from datetime import datetime
from pathlib import Path
import sys
import shutil
from rich.console import Console
from rich.prompt import Confirm

from .anki.anki_deck_creator import AnkiDeckCreator
from .vocab_entry import VocabEntry
from .tsv import read_from_file, write_to_file
from .llm.llm_factory import create_llm_client
from .llm.prompt_builder import PromptBuilder
from .logging import get_logger
from .settings import Settings
from .tts.tts_manager import TTSManager


class Pipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger("anker.pipeline")
        self.console = Console()

        self.prompt = PromptBuilder(settings).build()
        self.logger.debug("Loaded LLM instructions:\n%s", self.prompt)
        
        self.llm = create_llm_client(settings.llm)
        self.tts = TTSManager(settings.tts)
        self.anki_packager = AnkiDeckCreator(settings)

    def run(self) -> None:
        vocab = self._load_or_generate_vocabulary()

        if not self.settings.anki_output:
            self.logger.info("No anki_output specified; skipping TTS and Anki packaging")
            return
        
        self.tts.synthesize(vocab)

        self._build_anki(vocab)

        self._ask_and_save_result_to_few_shot_examples()
    
    def _confirm_step(self, prompt: str, *, default_yes: bool, ask_yes_no: bool = True) -> bool:
        """ Ask the user to confirm an action via stdin/stdout """
        if not self.settings.confirm_steps:
            return default_yes
        
        try:
            if ask_yes_no:
                return bool(Confirm.ask(f"[bold]{prompt}[/bold]", default=default_yes))
            self.console.print(f"[bold]{prompt}[/bold]")
            self.console.input("[dim]Press Enter to continue...[/dim]")
            return True
        except EOFError:
            return default_yes
    
    def _load_or_generate_vocabulary(self) -> list[VocabEntry]:
        # Use existing TSV if present and confirmed
        if self.settings.table_output and Path(self.settings.table_output).is_file():
            if self._confirm_step(
                "Use existing TSV vocabulary table? (If 'No', a new one will be generated, the old one will be discarded)",
                default_yes=True,
            ):
                vocab = read_from_file(Path(self.settings.table_output))
                self.logger.info("Using existing TSV table with %d vocabulary entries", len(vocab))
                return vocab

        # Otherwise, generate from text
        input_text = self._read_input_text()
        
        vocab = self.llm.generate_vocabulary(instructions=self.prompt, input_text=input_text)

        # Handle the TSV writing and reading after manual edits
        if not self.settings.table_output:
            self.logger.info("No table_output specified; skipping TSV writing")
            return vocab

        write_to_file(vocab, Path(self.settings.table_output))
        self.logger.info("Wrote TSV vocabulary table to %s", Path(self.settings.table_output).resolve().as_uri())

        if not self.settings.confirm_steps:
            return vocab

        # Pause to allow manual edits before proceeding
        self._confirm_step(
            "Review/edit the TSV file if needed, then press Enter to continue",
            default_yes=True,
            ask_yes_no=False,
        )
        vocab = read_from_file(Path(self.settings.table_output))
        return vocab

    def _read_input_text(self) -> str:
        if self.settings.text_input:
            path = Path(self.settings.text_input)
            self.logger.info("Reading input text from %s", path)
            return path.read_text(encoding="utf-8")
        self.logger.info("Reading input text from stdin")
        self.console.print("[bold]Reading input text from stdin[/bold] [dim](end with Ctrl-D)[/dim]")
        return sys.stdin.read()

    def _build_anki(self, vocab: list[VocabEntry]) -> None:
        output_file = Path(self.settings.anki_output)
        if output_file.is_file():
            if self._confirm_step(
                "The Anki deck file already exists! Overwrite it?",
                default_yes=True,
            ):
                output_file.unlink()
            else:
                self.logger.info("Skipping Anki deck generation, the existing deck file is kept")
                return

        self.anki_packager.write_anki_deck(vocab)
        self.logger.info("Wrote Anki deck to %s", output_file.resolve())
    
    def _ask_and_save_result_to_few_shot_examples(self) -> None:
        few_shot_dir = self.settings.llm.options.few_shot_examples
        if not (
            self.settings.table_output and Path(self.settings.table_output).is_file() and
            self.settings.text_input and Path(self.settings.text_input).is_file() and
            few_shot_dir and Path(few_shot_dir).is_dir() and
            self._confirm_step(
                f"Add the result of the current run to few-shot examples at {few_shot_dir}?",
                default_yes=False,
            )
        ):
            return
        
        new_file_name = datetime.now().strftime("%Y.%m.%d_%H:%M:%S")
        shutil.copy(Path(self.settings.text_input), Path(few_shot_dir) / f"{new_file_name}.txt")
        shutil.copy(Path(self.settings.table_output), Path(few_shot_dir) / f"{new_file_name}.tsv")
        self.logger.info("Added the results to few-shot examples as %s.txt and %s.tsv", new_file_name, new_file_name)

