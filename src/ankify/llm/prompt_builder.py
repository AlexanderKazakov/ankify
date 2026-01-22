from pathlib import Path
from typing import Any

from ..logging import get_logger
from ..settings import Settings
from .jinja2_prompt_formatter import PromptRenderer


class PromptBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = get_logger("ankify.llm.prompt_builder")

    def build(self) -> str:
        prompt_template = self._read_prompt_template()
        custom_instructions = self._read_custom_instructions()
        few_shot_examples = self._load_few_shot_examples()

        context: dict[str, Any] = {
            "note_type": self._settings.note_type,
            "language_a": self._settings.language_a,
            "language_b": self._settings.language_b,
            "custom_instructions": custom_instructions,
            "few_shot_examples": few_shot_examples,
        }

        return PromptRenderer.render(prompt_template, context)

    def _read_prompt_template(self) -> str:
        prompt_template = self._settings.llm.options.prompt_template
        if not prompt_template:
            raise ValueError("Prompt template must be set")
        path = Path(prompt_template).expanduser()
        if not path.is_file():
            raise ValueError(f"Prompt template file not found at {path.resolve()}")
        self._logger.info("Loaded prompt template from %s", path.resolve())
        return path.read_text(encoding="utf-8").strip()

    def _read_custom_instructions(self) -> str:
        path = self._settings.llm.options.custom_instructions
        if not path:
            self._logger.info("No custom instructions file specified; continuing without custom instructions")
            return ""
        p = Path(path).expanduser()
        if not p.is_file():
            raise RuntimeError(f"Custom instructions file not found at {p.resolve()}")
        self._logger.info("Loaded custom instructions from %s", p.resolve())
        return p.read_text(encoding="utf-8").strip()

    def _load_few_shot_examples(self) -> list[dict[str, str]]:
        examples_dir = self._settings.llm.options.few_shot_examples
        if not examples_dir:
            self._logger.info("No few-shot examples directory specified; continuing without few-shot examples")
            return []
        dir_path = Path(examples_dir).expanduser()
        if not dir_path.is_dir():
            raise RuntimeError(f"Few-shot examples directory not found at {dir_path.resolve()}")

        examples: list[dict[str, str]] = []
        for txt_file in sorted(dir_path.glob("*.txt")):
            tsv_file = txt_file.with_suffix(".tsv")
            if not tsv_file.is_file():
                # Skip when there is no matching TSV
                continue
            input_text = txt_file.read_text(encoding="utf-8").strip()
            output_text = tsv_file.read_text(encoding="utf-8").strip()
            examples.append({"input": input_text, "output": output_text})

        self._logger.info("Loaded %d few-shot examples from %s", len(examples), dir_path.resolve())
        return examples
