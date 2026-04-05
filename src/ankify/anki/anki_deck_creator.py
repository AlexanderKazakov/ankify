import hashlib
import secrets
import genanki
from pathlib import Path
from importlib import resources

from ..vocab_entry import VocabEntry
from ..logging import get_logger
from ..settings import ANKIFY_NOTE_TYPE_MODEL_NAME, NoteType


class AnkiDeckCreator:
    def __init__(self, output_file: Path, deck_name: str, note_type: NoteType) -> None:
        self.logger = get_logger("ankify.anki.anki_deck_creator")
        self.output_file = output_file
        self.deck_name = deck_name
        self._fix_genanki_sort_type()
        self.anki_note_model = self._create_anki_note_model(note_type)

    def write_anki_deck(self, vocab: list[VocabEntry]) -> None:
        if not vocab:
            self.logger.info("Empty vocabulary; skipping Anki deck creation")
            return

        self.logger.info("Creating Anki deck with %d notes", len(vocab))

        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        deck = genanki.Deck(AnkiGuidGenerator.random_int_guid(), self.deck_name)
        media_files = set()
        for entry in vocab:
            note = self._create_anki_note(entry)
            deck.add_note(note)
            media_files.add(str(entry.front_audio))
            media_files.add(str(entry.back_audio))

        package = genanki.Package(deck)
        package.media_files = list(media_files)

        self.logger.debug("Deck created. Writing it to %s", str(output_path.resolve()))
        package.write_to_file(str(output_path))

    def _create_anki_note(self, entry: VocabEntry) -> genanki.Note:
        note = genanki.Note(
            model=self.anki_note_model,
            fields=[
                entry.front,
                entry.back,
                entry.front_language,
                entry.back_language,
                f"[sound:{entry.front_audio.name}]",
                f"[sound:{entry.back_audio.name}]",
            ],
            guid=AnkiGuidGenerator.random_base91_guid(),
        )
        return note

    def _create_anki_note_model(self, note_type: NoteType) -> genanki.Model:
        def _load(package: str, filename: str) -> str:
            try:
                return (
                    resources.files(package)
                    .joinpath(filename)
                    .read_text(encoding="utf-8")
                )
            except Exception as exc:
                self.logger.error(
                    "Failed to load resource '%s' from package '%s'", filename, package
                )
                raise FileNotFoundError(
                    f"Resource not found: {package}/{filename}"
                ) from exc

        self.logger.info("Loading Anki note model from templates")

        css = _load("ankify.anki.templates", "styles.css")

        forward_qfmt = _load("ankify.anki.templates", "forward_qfmt.html")
        forward_afmt = _load("ankify.anki.templates", "forward_afmt.html")
        backward_qfmt = _load("ankify.anki.templates", "backward_qfmt.html")
        backward_afmt = _load("ankify.anki.templates", "backward_afmt.html")

        fields = [
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Front language"},
            {"name": "Back language"},
            {"name": "Front sound"},
            {"name": "Back sound"},
        ]

        if note_type == "basic_and_reversed":
            templates = [
                {
                    "name": "Forward Card",
                    "qfmt": forward_qfmt,
                    "afmt": forward_afmt,
                },
                {
                    "name": "Backward Card",
                    "qfmt": backward_qfmt,
                    "afmt": backward_afmt,
                },
            ]
        elif note_type == "basic":
            templates = [
                {
                    "name": "Forward Card",
                    "qfmt": forward_qfmt,
                    "afmt": forward_afmt,
                }
            ]
        else:
            raise ValueError(f"Invalid note type: {note_type}")

        model_name = ANKIFY_NOTE_TYPE_MODEL_NAME[note_type]
        model = genanki.Model(
            model_id=AnkiGuidGenerator.hash_based_int_guid(model_name),
            name=model_name,
            fields=fields,
            templates=templates,
            css=css,
        )
        self.logger.debug(
            "Created Anki note model '%s' with id '%d'", model_name, model.model_id
        )
        return model

    def _fix_genanki_sort_type(self) -> None:
        # Ensure the cards default sort key is Date Added, not first or any other field.
        # Necessary to prevent disruption of the default normal sorting order in the Anki browser.
        try:
            import genanki.apkg_col as _apkg_col

            _apkg_col.APKG_COL = _apkg_col.APKG_COL.replace(
                '"sortType": "noteFld"', '"sortType": "noteCrt"'
            )
            if _apkg_col.APKG_COL.find('"sortType": "noteCrt"') == -1:
                raise RuntimeError("Failed to patch the sortType in genanki")
        except Exception as exc:
            self.logger.error(
                "Failed to adjust sortType in genanki, "
                "the normal sorting order in the Anki browser may be disrupted after loading the deck. "
                "Error: %s",
                exc,
                exc_info=True,
            )


class AnkiGuidGenerator:
    # Anki-style base91 alphabet used by genanki and Anki for GUIDs
    # fmt: off
    _ANKI_BASE91_TABLE = [
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's',
        't', 'u', 'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L',
        'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4',
        '5', '6', '7', '8', '9', '!', '#', '$', '%', '&', '(', ')', '*', '+', ',', '-', '.', '/', ':',
        ';', '<', '=', '>', '?', '@', '[', ']', '^', '_', '`', '{', '|', '}', '~'
    ]
    # fmt: on

    @staticmethod
    def random_int_guid() -> int:
        # random positive integer from signed 64-bit integer range
        n = 0
        while n == 0:
            n = secrets.randbits(63)
        return n

    @staticmethod
    def random_base91_guid() -> str:
        # random_int_guid() -> encode with Anki/base91 alphabet
        return AnkiGuidGenerator._encode_base91(AnkiGuidGenerator.random_int_guid())

    @staticmethod
    def hash_based_int_guid(data: str) -> int:
        # hash(data) -> truncate to signed 64-bit integer range
        m = hashlib.sha256()
        m.update(data.encode("utf-8"))
        hash_bytes = m.digest()[:8]
        value = 0
        for b in hash_bytes:
            value <<= 8
            value += b
        # Truncate to positive signed 64-bit integer range [1, 2^63-1]
        value &= (1 << 63) - 1
        if value == 0:
            value = 1
        return value

    @staticmethod
    def hash_based_base91_guid(data: str) -> str:
        # hash_based_int_guid() -> encode with Anki/base91 alphabet
        return AnkiGuidGenerator._encode_base91(
            AnkiGuidGenerator.hash_based_int_guid(data)
        )

    @staticmethod
    def _encode_base91(value: int) -> str:
        # Convert positive integer to base91 string using Anki alphabet
        if value <= 0:
            raise ValueError("Value must be positive")
        table = AnkiGuidGenerator._ANKI_BASE91_TABLE
        base = len(table)
        chars: list[str] = []
        while value > 0:
            value, rem = divmod(value, base)
            chars.append(table[rem])
        chars.reverse()
        return "".join(chars)
