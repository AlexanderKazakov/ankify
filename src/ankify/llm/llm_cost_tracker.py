import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from decimal import Decimal
from math import floor, log10
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from io import StringIO

from rich.console import Console
from rich.table import Table
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, before_sleep_log
from openai.types.completion_usage import CompletionUsage
from openai.types.responses.response_usage import ResponseUsage


_logger = logging.getLogger(__name__)


@dataclass
class LLMPricing:
    cached_input: Decimal = Decimal(0)
    uncached_input: Decimal = Decimal(0)
    reasoning: Decimal = Decimal(0)
    output: Decimal = Decimal(0)
    
    @property
    def is_valid(self) -> bool:
        return (
            self.cached_input > 0 and self.uncached_input > 0 and self.reasoning > 0 and self.output > 0 and
            self.cached_input <= self.uncached_input and self.reasoning <= self.output
        )


@dataclass
class LLMTokenUsage:
    cached_input: int = 0
    uncached_input: int = 0
    reasoning: int = 0
    output: int = 0
    total: int = 0
    
    @property
    def is_valid(self) -> bool:
        return (
            self.cached_input + self.uncached_input + self.reasoning + self.output == self.total and
            self.cached_input >= 0 and self.uncached_input >= 0 and self.reasoning >= 0 and self.output >= 0
        )
    
    @classmethod
    def from_openai_usage(cls, usage: CompletionUsage | ResponseUsage) -> "LLMTokenUsage":
        try:
            if isinstance(usage, CompletionUsage):
                return cls._from_openai_completion_usage(usage)
            elif isinstance(usage, ResponseUsage):
                return cls._from_openai_response_usage(usage)
            else:
                raise ValueError(f"Unsupported usage type: {type(usage)}")
        except Exception as e:
            _logger.warning("Failed to parse token usage: %s", e)
            return cls(0, 0, 0, 0, 0)
    
    @classmethod
    def _from_openai_completion_usage(cls, usage: CompletionUsage) -> "LLMTokenUsage":
        cached = 0
        if usage.prompt_tokens_details is not None:
            cached = usage.prompt_tokens_details.cached_tokens
        reasoning = 0
        if usage.completion_tokens_details is not None:
            reasoning = usage.completion_tokens_details.reasoning_tokens
        res = cls(
            cached_input=cached,
            uncached_input=usage.prompt_tokens - cached,
            reasoning=reasoning,
            output=usage.completion_tokens - reasoning,
            total=usage.total_tokens
        )
        if not res.is_valid:
            _logger.warning("Token usage is not valid: %s, openai.CompletionUsage: %s", res, usage)
        return res
    
    @classmethod
    def _from_openai_response_usage(cls, usage: ResponseUsage) -> "LLMTokenUsage":
        cached = 0
        if usage.input_tokens_details is not None:
            cached = usage.input_tokens_details.cached_tokens
        reasoning = 0
        if usage.output_tokens_details is not None:
            reasoning = usage.output_tokens_details.reasoning_tokens
        res = cls(
            cached_input=cached,
            uncached_input=usage.input_tokens - cached,
            reasoning=reasoning,
            output=usage.output_tokens - reasoning,
            total=usage.total_tokens,
        )
        if not res.is_valid:
            _logger.warning("Token usage is not valid: %s, openai.ResponseUsage: %s", res, usage)
        return res
        
    def __add__(self, other: "LLMTokenUsage") -> "LLMTokenUsage":
        return self.__class__(
            cached_input=self.cached_input + other.cached_input,
            uncached_input=self.uncached_input + other.uncached_input,
            reasoning=self.reasoning + other.reasoning,
            output=self.output + other.output,
            total=self.total + other.total
        )
    
    def __radd__(self, other: int) -> "LLMTokenUsage":
        return self if other == 0 else NotImplemented


@dataclass
class LLMCost:
    cached_input: Decimal = Decimal(0)
    uncached_input: Decimal = Decimal(0)
    reasoning: Decimal = Decimal(0)
    output: Decimal = Decimal(0)
    total: Decimal = Decimal(0)
    
    @property
    def is_valid(self) -> bool:
        return (
            self.total == self.cached_input + self.uncached_input + self.reasoning + self.output and
            self.cached_input >= 0 and self.uncached_input >= 0 and self.reasoning >= 0 and self.output >= 0
        )
    
    @classmethod
    def calculate(cls, token_usage: LLMTokenUsage, pricing: LLMPricing) -> "LLMCost":
        cached_input = token_usage.cached_input * pricing.cached_input
        uncached_input = token_usage.uncached_input * pricing.uncached_input
        reasoning = token_usage.reasoning * pricing.reasoning
        output = token_usage.output * pricing.output
        res = cls(
            cached_input=cached_input,
            uncached_input=uncached_input,
            reasoning=reasoning,
            output=output,
            total=cached_input + uncached_input + reasoning + output
        )
        if not res.is_valid:
            _logger.warning("Cost is not valid: %s", res)
        return res
    
    def __add__(self, other: "LLMCost") -> "LLMCost":
        return self.__class__(
            cached_input=self.cached_input + other.cached_input,
            uncached_input=self.uncached_input + other.uncached_input,
            reasoning=self.reasoning + other.reasoning,
            output=self.output + other.output,
            total=self.total + other.total
        )
    
    def __radd__(self, other: int) -> "LLMCost":
        return self if other == 0 else NotImplemented


class LLMPricingLoader:
    """
    Download and cache pricing data for LLM models.
    Singleton to avoid re-loading from disk.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
            self, 
            *,
            cache_dir: Path | None = None,
            cache_duration: timedelta = timedelta(hours=24),
            source_url: str = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
        ):
        """
        cache_dir: The directory to cache the pricing data, default is ~/.cache/llm_cost_tracker
        cache_duration: Pricing data cache invalidation duration
        source_url: The URL to fetch the pricing data
        """
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._loaded_models_pricing: dict[str, LLMPricing] = {}

        self._cache_dir = cache_dir or Path.home() / ".cache" / "llm_cost_tracker"
        self._cache_duration = cache_duration
        self._source_url = source_url
        self._cache_file = self._cache_dir / "llm_pricing.json"

    def get_pricing(self, model: str) -> LLMPricing:
        if model in self._loaded_models_pricing:
            return self._loaded_models_pricing[model]

        data = self._get_data()
        model_data = self._resolve_model_pricing(data, model)
        if model_data is None:
            _logger.warning("Model %s not found in pricing data, return all zeros", model)
            self._loaded_models_pricing[model] = LLMPricing()
            return self._loaded_models_pricing[model]
        
        pricing = LLMPricing()
        
        if "input_cost_per_token" in model_data:
            pricing.uncached_input = Decimal(model_data["input_cost_per_token"])
        else:
            _logger.warning("No input token cost found for model %s, return all zeros", model)
            self._loaded_models_pricing[model] = LLMPricing()
            return self._loaded_models_pricing[model]
        
        if "cache_read_input_token_cost" in model_data:
            pricing.cached_input = Decimal(model_data["cache_read_input_token_cost"])
        else:
            _logger.info("No cached input token cost found for model %s, set it to the input token cost", model)
            pricing.cached_input = pricing.uncached_input
        
        if "output_cost_per_token" in model_data:
            pricing.output = Decimal(model_data["output_cost_per_token"])
        else:
            _logger.warning("No output token cost found for model %s, return all zeros", model)
            self._loaded_models_pricing[model] = LLMPricing()
            return self._loaded_models_pricing[model]
        
        pricing.reasoning = pricing.output
        
        if not pricing.is_valid:
            _logger.warning("Pricing data for model %s is not valid: %s", model, pricing)
        
        self._loaded_models_pricing[model] = pricing
        return self._loaded_models_pricing[model]

    def _resolve_model_pricing(self, data: dict[str, Any], model: str) -> dict[str, Any] | None:
        if model in data:
            return data[model]

        for key in data.keys():
            if model in key:
                _logger.warning("Found only fuzzy match for pricing model name: %s -> %s", model, key)
                return data[key]

        return None
    
    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_cache_valid(self) -> bool:
        """Check if cached pricing data is still valid."""
        if not self._cache_file.exists():
            return False

        cache_age = datetime.now() - datetime.fromtimestamp(self._cache_file.stat().st_mtime)
        return cache_age < self._cache_duration

    def _load_cached_pricing(self) -> dict[str, Any] | None:
        """Load pricing data from cache if valid."""
        if not self._is_cache_valid():
            return None

        try:
            with open(self._cache_file, encoding="utf-8") as f:
                data = json.load(f, parse_float=Decimal)
            _logger.debug("Loaded pricing data from cache %s", self._cache_file)
            return data
        except Exception as e:
            _logger.warning("Failed to load cached pricing data: %s", e)
            return None

    def _save_to_cache(self, data: dict[str, Any]) -> None:
        """Save pricing data to cache."""
        try:
            self._ensure_cache_dir()
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            _logger.debug("Saved pricing data to cache %s", self._cache_file)
        except Exception as e:
            _logger.warning("Failed to save pricing data to cache: %s", e)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type((URLError, HTTPError)),
        before_sleep=before_sleep_log(_logger, logging.WARNING)
    )
    def _fetch_from_url(self) -> dict[str, Any]:
        """Fetch pricing data from remote URL."""
        _logger.info("Fetching model pricing data from %s", self._source_url)
        with urlopen(self._source_url, timeout=30.0) as response:
            data = json.loads(response.read().decode("utf-8"), parse_float=Decimal)
        return data

    def _get_data(self) -> dict[str, Any]:
        """
        Get pricing data, using cache if available and valid.

        Returns cached data if it's less than 24 hours old,
        otherwise fetches fresh data from the remote URL.
        """
        # Try to load from cache first
        cached_data = self._load_cached_pricing()
        if cached_data is not None:
            return cached_data

        # Fetch fresh data
        data = self._fetch_from_url()
        self._save_to_cache(data)
        return data


@dataclass
class LLMUsage:
    model: str
    pricing: LLMPricing
    token_usage: LLMTokenUsage
    cost: LLMCost
    num_calls: int = 1

    @classmethod
    def from_openai_usage(cls, model: str, openai_usage: CompletionUsage) -> "LLMUsage":
        """Converts OpenAI token usage data into a clearer structure with costs and rich-printable table"""
        pricing = LLMPricingLoader().get_pricing(model)
        token_usage = LLMTokenUsage.from_openai_usage(openai_usage)
        cost = LLMCost.calculate(token_usage, pricing)
        return cls(model, pricing, token_usage, cost, 1)

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        if self.model != other.model:
            raise ValueError("Models must be the same to add the LLM usage")
        return self.__class__(
            model=self.model,
            pricing=self.pricing,
            token_usage=self.token_usage + other.token_usage,
            cost=self.cost + other.cost,
            num_calls=self.num_calls + other.num_calls
        )

    def __radd__(self, other: int) -> "LLMUsage":
        return self if other == 0 else NotImplemented

    def print_table(self) -> None:
        table = self._build_rich_table()
        console = Console()
        console.print(table)
        console.print()
    
    def table_to_string(self) -> str:
        table = self._build_rich_table()
        buffer = StringIO()
        console = Console(record=True, file=buffer)
        console.print(table)
        console.print()
        return console.export_text()

    def _build_rich_table(self) -> Table:
        cost_formatter = _create_cost_formatter(_determine_cost_decimals(self.cost))
        
        table = Table(
            title=f"[bold cyan]LLM API Usage Breakdown, $[/bold cyan]\n[dim]Model: {self.model}, number of calls: {self.num_calls}[/dim]", 
            title_justify="center",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            show_lines=True
        )
        
        table.add_column("Token Type", style="cyan", justify="left", min_width=20)
        table.add_column("Count", style="green", justify="right", min_width=15)
        table.add_column("Price per 1M", style="yellow", justify="right", min_width=15)
        table.add_column("Cost", style="bright_green", justify="right", min_width=15)
        
        # Add rows for each token type
        table.add_row(
            "Cached Input",
            f"{self.token_usage.cached_input:,}",
            f"${self.pricing.cached_input * 1_000_000:,.2f}",
            cost_formatter(self.cost.cached_input)
        )
        
        table.add_row(
            "Uncached Input",
            f"{self.token_usage.uncached_input:,}",
            f"${self.pricing.uncached_input * 1_000_000:,.2f}",
            cost_formatter(self.cost.uncached_input)
        )
        
        table.add_row(
            "Reasoning",
            f"{self.token_usage.reasoning:,}",
            f"${self.pricing.reasoning * 1_000_000:,.2f}",
            cost_formatter(self.cost.reasoning)
        )
        
        table.add_row(
            "Output",
            f"{self.token_usage.output:,}",
            f"${self.pricing.output * 1_000_000:,.2f}",
            cost_formatter(self.cost.output)
        )
        
        # Add separator and total row
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{self.token_usage.total:,}[/bold]",
            "[dim]—[/dim]",
            f"[bold]{cost_formatter(self.cost.total)}[/bold]"
        )
        
        return table


def _determine_cost_decimals(cost: LLMCost) -> int:
    # Determine consistent decimal places for the entire "Cost" column
    values = [cost.cached_input, cost.uncached_input, cost.reasoning, cost.output, cost.total]

    # Always at least cents (2)
    non_zero_values = [v for v in values if v != 0]
    if not non_zero_values:
        return 2
    min_non_zero = min(non_zero_values)
    if min_non_zero >= 1:
        return 2
    
    # For values < 1$, ensure at least 2 significant digits are shown across the column
    a = -floor(log10(float(min_non_zero)))
    return max(2, a + 1)


def _create_cost_formatter(cost_decimals: int):
    def cost_formatter(value: Decimal) -> str:
        if value == 0:
            return "$0"
        
        format = "${value:,." + str(cost_decimals) + "f}"
        return format.format(value=value)

    return cost_formatter


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    base_url = os.getenv("OPENAI_BASE_URL") or None
    model = "gpt-5-nano"
    # model = "claude-4.5-haiku"
    client = OpenAI(api_key=api_key, base_url=base_url)

    question = "Give one sentence about why the sky looks blue."
    instructions = "Answer briefly and clearly."
    print("\nChat completion demo")
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": question},
        ],
    )
    chat_answer = chat.choices[0].message.content
    print(f"Q: {question}")
    print(f"A: {chat_answer}")
    LLMUsage.from_openai_usage(model, chat.usage).print_table()

    print("\nResponses API demo")
    response = client.responses.create(
        model=model,
        input=question,
        instructions=instructions,
    )
    response_answer = response.output_text
    print(f"Q: {question}")
    print(f"A: {response_answer}")
    LLMUsage.from_openai_usage(model, response.usage).print_table()
