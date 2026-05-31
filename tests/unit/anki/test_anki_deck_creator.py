"""Integration tests for AnkiDeckCreator."""

import sqlite3
import zipfile
from pathlib import Path

import pytest

from ankify.anki.anki_deck_creator import AnkiDeckCreator
from ankify.vocab_entry import VocabEntry


def _read_cards(apkg_path: Path, extract_dir: Path) -> list[tuple[int, int, int]]:
    """Return (note_id, card_ord, due) rows from the apkg's cards table."""
    with zipfile.ZipFile(apkg_path) as archive:
        archive.extract("collection.anki2", extract_dir)
    conn = sqlite3.connect(str(extract_dir / "collection.anki2"))
    try:
        return conn.execute(
            "SELECT nid, ord, due FROM cards ORDER BY nid, ord"
        ).fetchall()
    finally:
        conn.close()


class TestAnkiDeckCreator:
    """Tests for AnkiDeckCreator class."""

    @pytest.fixture
    def temp_audio_files(self, tmp_path):
        """Create temporary audio files for testing."""
        front_audio = tmp_path / "front.mp3"
        back_audio = tmp_path / "back.mp3"
        front_audio.write_bytes(b"fake front audio")
        back_audio.write_bytes(b"fake back audio")
        return front_audio, back_audio

    @pytest.fixture
    def sample_entries(self, temp_audio_files):
        """Create sample vocabulary entries with audio."""
        front_audio, back_audio = temp_audio_files
        return [
            VocabEntry(
                front="Hello",
                back="Hallo",
                front_language="English",
                back_language="German",
                front_audio=front_audio,
                back_audio=back_audio,
            ),
            VocabEntry(
                front="World",
                back="Welt",
                front_language="English",
                back_language="German",
                front_audio=front_audio,
                back_audio=back_audio,
            ),
        ]

    def test_creator_basic_model(self, tmp_path):
        """Creator creates basic model with one template."""
        output_file = tmp_path / "test.apkg"
        creator = AnkiDeckCreator(output_file, "Test", "basic")

        # basic should have 1 template
        assert len(creator.anki_note_model.templates) == 1
        assert creator.anki_note_model.name == "Ankify Basic"

    def test_creator_basic_and_reversed_model(self, tmp_path):
        """Creator creates basic_and_reversed model with two templates."""
        output_file = tmp_path / "test.apkg"
        creator = AnkiDeckCreator(output_file, "Test", "basic_and_reversed")

        # basic_and_reversed should have 2 templates
        assert len(creator.anki_note_model.templates) == 2
        assert creator.anki_note_model.name == "Ankify Basic & Reversed"

    def test_creator_invalid_note_type_raises(self, tmp_path):
        """Creator raises ValueError for invalid note type."""
        output_file = tmp_path / "test.apkg"

        with pytest.raises(ValueError, match="Invalid note type"):
            AnkiDeckCreator(output_file, "Test", "invalid")

    def test_write_anki_deck_creates_file(self, tmp_path, sample_entries):
        """write_anki_deck creates .apkg file."""
        output_file = tmp_path / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic")

        creator.write_anki_deck(sample_entries)

        assert output_file.exists()
        # File should have some content
        assert output_file.stat().st_size > 0

    def test_write_anki_deck_empty_vocab(self, tmp_path):
        """write_anki_deck handles empty vocabulary."""
        output_file = tmp_path / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic")

        creator.write_anki_deck([])

        # File should not be created for empty vocab
        assert not output_file.exists()

    def test_write_anki_deck_creates_parent_dirs(self, tmp_path, sample_entries):
        """write_anki_deck creates parent directories if needed."""
        output_file = tmp_path / "nested" / "dir" / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic")

        creator.write_anki_deck(sample_entries)

        assert output_file.exists()

    def test_model_has_six_fields(self, tmp_path):
        """Note model has all six required fields."""
        output_file = tmp_path / "test.apkg"
        creator = AnkiDeckCreator(output_file, "Test", "basic")

        field_names = [f["name"] for f in creator.anki_note_model.fields]
        expected = [
            "Front",
            "Back",
            "Front language",
            "Back language",
            "Front sound",
            "Back sound",
        ]
        assert field_names == expected


class TestAnkiDeckCreatorNotes:
    """Tests for note creation."""

    @pytest.fixture
    def temp_audio_files(self, tmp_path):
        """Create temporary audio files for testing."""
        front_audio = tmp_path / "front.mp3"
        back_audio = tmp_path / "back.mp3"
        front_audio.write_bytes(b"audio")
        back_audio.write_bytes(b"audio")
        return front_audio, back_audio

    def test_create_anki_note(self, tmp_path, temp_audio_files):
        """_create_anki_note creates genanki.Note with correct fields."""
        front_audio, back_audio = temp_audio_files
        output_file = tmp_path / "test.apkg"
        creator = AnkiDeckCreator(output_file, "Test", "basic")

        entry = VocabEntry(
            front="Hello",
            back="Hallo",
            front_language="English",
            back_language="German",
            front_audio=front_audio,
            back_audio=back_audio,
        )

        note = creator._create_anki_note(entry)

        assert note.fields[0] == "Hello"
        assert note.fields[1] == "Hallo"
        assert note.fields[2] == "English"
        assert note.fields[3] == "German"
        assert "[sound:" in note.fields[4]
        assert "[sound:" in note.fields[5]

    def test_note_has_guid(self, tmp_path, temp_audio_files):
        """Created note has a GUID."""
        front_audio, back_audio = temp_audio_files
        output_file = tmp_path / "test.apkg"
        creator = AnkiDeckCreator(output_file, "Test", "basic")

        entry = VocabEntry(
            front="Hello",
            back="Hallo",
            front_language="English",
            back_language="German",
            front_audio=front_audio,
            back_audio=back_audio,
        )

        note = creator._create_anki_note(entry)

        assert note.guid is not None
        assert len(note.guid) > 0


class TestAnkiDeckCreatorPackaging:
    """Tests for deck packaging."""

    @pytest.fixture
    def temp_audio_files(self, tmp_path):
        """Create temporary audio files for testing."""
        front_audio = tmp_path / "front.mp3"
        back_audio = tmp_path / "back.mp3"
        front_audio.write_bytes(b"front audio content")
        back_audio.write_bytes(b"back audio content")
        return front_audio, back_audio

    def test_deck_includes_media_files(self, tmp_path, temp_audio_files, mocker):
        """Written deck package includes media files."""
        front_audio, back_audio = temp_audio_files
        output_file = tmp_path / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic")

        entry = VocabEntry(
            front="Hello",
            back="Hallo",
            front_language="English",
            back_language="German",
            front_audio=front_audio,
            back_audio=back_audio,
        )

        mock_genanki = mocker.patch("ankify.anki.anki_deck_creator.genanki")
        mock_deck = mocker.MagicMock()
        mock_package = mocker.MagicMock()
        mock_genanki.Deck.return_value = mock_deck
        mock_genanki.Package.return_value = mock_package
        mock_genanki.Note = mocker.MagicMock()
        mock_genanki.Model = mocker.MagicMock()

        # Don't actually create model - use a mock
        creator.anki_note_model = mocker.MagicMock()

        creator.write_anki_deck([entry])

        # Verify media files were set
        assert mock_package.media_files is not None
        assert len(mock_package.media_files) == 2


class TestAnkiDeckCardOrdering:
    """Tests that cards get incrementing positions so siblings stay together."""

    @pytest.fixture
    def temp_audio_files(self, tmp_path):
        """Create temporary audio files for testing."""
        front_audio = tmp_path / "front.mp3"
        back_audio = tmp_path / "back.mp3"
        front_audio.write_bytes(b"audio")
        back_audio.write_bytes(b"audio")
        return front_audio, back_audio

    def _entries(self, count, audio):
        front_audio, back_audio = audio
        return [
            VocabEntry(
                front=f"front{i}",
                back=f"back{i}",
                front_language="English",
                back_language="German",
                front_audio=front_audio,
                back_audio=back_audio,
            )
            for i in range(count)
        ]

    def test_basic_cards_get_incrementing_positions(self, tmp_path, temp_audio_files):
        """Each basic note's single card gets a distinct, increasing position."""
        output_file = tmp_path / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic")

        creator.write_anki_deck(self._entries(3, temp_audio_files))

        rows = _read_cards(output_file, tmp_path)
        dues = sorted(due for _, _, due in rows)
        assert dues == [1, 2, 3]

    def test_basic_and_reversed_sibling_cards_share_position(
        self, tmp_path, temp_audio_files
    ):
        """Forward and reverse cards of one note share the same position."""
        output_file = tmp_path / "output.apkg"
        creator = AnkiDeckCreator(output_file, "Test Deck", "basic_and_reversed")

        creator.write_anki_deck(self._entries(3, temp_audio_files))

        rows = _read_cards(output_file, tmp_path)

        # 3 notes x 2 cards (forward + reverse)
        assert len(rows) == 6

        due_by_note: dict[int, dict[int, int]] = {}
        for nid, card_ord, due in rows:
            due_by_note.setdefault(nid, {})[card_ord] = due

        # both cards of every note share the same position
        for ords in due_by_note.values():
            assert ords[0] == ords[1]

        # notes have distinct, increasing positions starting at 1 (not all 0)
        note_positions = sorted(ords[0] for ords in due_by_note.values())
        assert note_positions == [1, 2, 3]


class TestGenankinSortTypeFix:
    """Tests for the genanki sort type fix."""

    def test_fix_genanki_sort_type_called(self, tmp_path, mocker):
        """_fix_genanki_sort_type is called during initialization."""
        mock_fix = mocker.patch.object(AnkiDeckCreator, "_fix_genanki_sort_type")
        output_file = tmp_path / "test.apkg"
        AnkiDeckCreator(output_file, "Test", "basic")

        mock_fix.assert_called_once()
