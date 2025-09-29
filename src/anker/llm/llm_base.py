from abc import ABC, abstractmethod
from pathlib import Path

from ..vocab_entry import VocabEntry
from ..tsv import read_from_string
from ..logging import get_logger


class LLMClient(ABC):
    def __init__(self) -> None:
        self._logger = get_logger(f"anker.llm.{self.__class__.__name__}")

    def generate_vocabulary(self, instructions: str, input_text: str) -> list[VocabEntry]:
        self._logger.info("Generating vocabulary entries with LLM")
        llm_answer = self._call_llm(instructions=instructions, input_text=input_text)
        vocab = self._parse_llm_answer(llm_answer)
        self._logger.info("Generated %d vocabulary entries", len(vocab))
        return vocab

    @abstractmethod
    def _call_llm(self, instructions: str, input_text: str) -> str:
        raise NotImplementedError

    def _parse_llm_answer(self, llm_answer: str) -> list[VocabEntry]:
        self._logger.info("Parsing LLM answer into vocabulary entries")
        return read_from_string(llm_answer)
    

