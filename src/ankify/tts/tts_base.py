from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tts_cost_tracker import TTSCostTracker


class TTSSingleLanguageClient(ABC):
    @abstractmethod
    def synthesize(
        self,
        entities: dict[str, bytes | None],
        language: str,
        cost_tracker: "TTSCostTracker | None" = None,
    ) -> None:
        """
        Text-to-Speech synthesis for a single fixed language and settings.
        For each item, the audio (binary) is synthesized and stored in the dictionary.
        """
        raise NotImplementedError
