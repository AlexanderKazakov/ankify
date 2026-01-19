from abc import ABC, abstractmethod
import time

from ..vocab_entry import VocabEntry
from ..tsv import read_from_string
from ..logging import get_logger
from .llm_cost_tracker import LLMUsage


class LLMClient(ABC):
    def __init__(self, model: str) -> None:
        self._model = model
        self._logger = get_logger(f"ankify.llm.{self.__class__.__name__}")

    def generate_vocabulary(self, instructions: str, input_text: str) -> list[VocabEntry]:
        self._logger.info("Generating vocabulary entries with LLM")
        start_time = time.time()
        llm_answer, llm_usage = self._call_llm(instructions=instructions, input_text=input_text)
        end_time = time.time()
        self._logger.info("LLM call took %.2f seconds", end_time - start_time)
        LLMUsage.from_openai_usage(self._model, llm_usage).print_table()
        vocab = self._parse_llm_answer(llm_answer)
        self._logger.info("Generated %d vocabulary entries", len(vocab))
        return vocab

    @abstractmethod
    def _call_llm(self, instructions: str, input_text: str) -> tuple[str, dict]:
        raise NotImplementedError

    def _parse_llm_answer(self, llm_answer: str) -> list[VocabEntry]:
        self._logger.info("Parsing LLM answer into vocabulary entries")
        return read_from_string(llm_answer)
    

