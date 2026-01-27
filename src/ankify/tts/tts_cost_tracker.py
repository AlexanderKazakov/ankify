from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass, field
from collections import defaultdict
from typing import DefaultDict

from ..logging import get_logger


@dataclass
class EngineUsage:
    chars: int = 0
    cost: Decimal = field(default_factory=lambda: Decimal("0.00"))


@dataclass
class LanguageUsageKey:
    language: str
    engine: str

    def __hash__(self) -> int:
        return hash((self.language, self.engine))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LanguageUsageKey):
            return False
        return self.language == other.language and self.engine == other.engine


class TTSCostTracker(ABC):
    """
    Abstract base class for TTS cost trackers.
    Accumulates usage and provides a summary.
    """

    def __init__(self, provider_name: str):
        self._logger = get_logger(f"ankify.tts.{provider_name}.cost")
        self._provider_name = provider_name
        self._usage: DefaultDict[LanguageUsageKey, EngineUsage] = defaultdict(EngineUsage)

    @abstractmethod
    def _get_rate(self, engine: str | None) -> Decimal:
        """
        Get the rate per 1,000,000 characters for the given engine type.
        """
        raise NotImplementedError

    def calculate_cost(self, text: str, engine: str | None) -> Decimal:
        """
        Calculate the cost for synthesizing the given text with the specified engine.
        Does NOT accumulate usage.
        """
        if not text:
            return Decimal("0.00")

        rate = self._get_rate(engine)
        chars = len(text)
        cost = (Decimal(chars) / Decimal("1_000_000")) * rate
        return cost

    def track_usage(self, text: str, engine: str | None, language: str | None = None) -> None:
        """
        Calculate cost and accumulate usage stats by language and engine.
        """
        if not text:
            return

        cost = self.calculate_cost(text, engine)
        chars = len(text)

        engine_key = engine.lower() if engine else "default"
        language_key = language.lower() if language else "unknown"
        key = LanguageUsageKey(language=language_key, engine=engine_key)
        self._usage[key].chars += chars
        self._usage[key].cost += cost

    def log_summary(self) -> None:
        """
        Log a summary of accumulated costs by language and engine.
        """
        if not self._usage:
            return

        self._logger.info(f"{self._provider_name} TTS usage summary:")

        total_chars = 0
        total_cost = Decimal("0.00")

        for key, usage in sorted(self._usage.items(), key=lambda x: (x[0].language, x[0].engine)):
            self._logger.info(
                f"  {key.language} ({key.engine} engine): {usage.chars:,} characters, ${usage.cost:.4f}"
            )
            total_chars += usage.chars
            total_cost += usage.cost

        self._logger.info(f"  total: {total_chars:,} characters, ${total_cost:.4f}")


class AWSPollyCostTracker(TTSCostTracker):
    """
    Cost tracker for AWS Polly.
    Prices as of Jan 2026.
    """

    # AWS Polly pricing per 1,000,000 characters
    STANDARD_RATE = Decimal("4.00")
    NEURAL_RATE = Decimal("16.00")
    LONG_FORM_RATE = Decimal("100.00")
    GENERATIVE_RATE = Decimal("30.00")

    def __init__(self):
        super().__init__("AWS Polly")

    def _get_rate(self, engine: str | None) -> Decimal:
        engine_type = engine.lower() if engine else "standard"
        if engine_type == "neural":
            return self.NEURAL_RATE
        elif "long-form" in engine_type:
            return self.LONG_FORM_RATE
        elif "generative" in engine_type:
            return self.GENERATIVE_RATE
        else:
            return self.STANDARD_RATE


class AzureTTSCostTracker(TTSCostTracker):
    """
    Cost tracker for Azure Cognitive Services TTS.
    Prices as of Jan 2026.
    """

    # Azure TTS pricing per 1,000,000 characters
    NEURAL_RATE = Decimal("15.00")
    NEURAL_HD_RATE = Decimal("30.00")

    def __init__(self):
        super().__init__("Azure TTS")

    def _get_rate(self, engine: str | None) -> Decimal:
        engine_type = engine.lower() if engine else "neural"
        if "hd" in engine_type:
            return self.NEURAL_HD_RATE
        else:
            return self.NEURAL_RATE


class EdgeTTSCostTracker(TTSCostTracker):
    """
    Cost tracker for Edge TTS.
    Edge TTS is free, but we still track character counts.
    """

    def __init__(self):
        super().__init__("Edge TTS")

    def _get_rate(self, engine: str | None) -> Decimal:
        return Decimal("0.00")


class MultiProviderCostTracker:
    """
    Aggregates cost tracking across multiple TTS providers.
    """

    def __init__(self):
        self._logger = get_logger("ankify.tts.cost")
        self._trackers: dict[str, TTSCostTracker] = {}

    def get_tracker(self, provider: str) -> TTSCostTracker:
        """
        Get or create a cost tracker for the given provider.
        """
        if provider not in self._trackers:
            if provider == "aws":
                self._trackers[provider] = AWSPollyCostTracker()
            elif provider == "azure":
                self._trackers[provider] = AzureTTSCostTracker()
            elif provider == "edge":
                self._trackers[provider] = EdgeTTSCostTracker()
            else:
                raise ValueError(f"Unknown TTS provider: {provider}")
        return self._trackers[provider]

    def log_summary(self) -> None:
        """
        Log summaries for all providers that have usage.
        """
        for tracker in self._trackers.values():
            tracker.log_summary()
