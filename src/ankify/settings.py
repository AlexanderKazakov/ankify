from pathlib import Path
from typing import Literal, Any

import yaml

from pydantic import BaseModel, Field, SecretStr, ConfigDict
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource


class StrictModel(BaseModel):
    """Base for nested config models; forbids unknown fields to catch YAML typos."""
    model_config = ConfigDict(extra="forbid")


class LLMOptions(StrictModel):
    """Provider-agnostic options that control prompt construction and model choice."""

    model: str = Field(
        default="gpt-5",
        description="LLM model identifier to use (e.g., gpt-4o, gpt-5).",
    )
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = Field(
        default=None,
        description="Reasoning effort for reasoning models",
    )
    prompt_template: Path = Field(
        default=Path("./settings/prompts/prompt_template.md.j2"),
        description="Path to the prompt or Jinja2 template file used to build the final prompt.",
    )
    custom_instructions: Path | None = Field(
        default=None,
        description="Optional file with additional instructions to inline into the prompt.",
    )
    few_shot_examples: Path | None = Field(
        default=None,
        description=(
            "Optional directory with few-shot examples to inline into the prompt. "
            "Each example is a pair of files sharing the same stem: N.txt (input) and N.tsv (expected output)."
        ),
    )


class OpenAIProviderAccess(StrictModel):
    """OpenAI-compatible API provider credentials."""

    api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI-compatible API key. Can be provided via env",
    )
    base_url: str | None = Field(
        default=None,
        description="URL of the openai-compatible API. `None` for for OpenAI itself. Can be provided via env",
    )

class LLMConfig(StrictModel):
    """LLM configuration: provider selection, runtime options, and credentials."""

    provider: Literal["openai"] = Field(
        default="openai",
        description="Which LLM provider backend to use.",
    )
    options: LLMOptions = Field(
        default_factory=LLMOptions,
        description="Provider-agnostic LLM options such as model and prompt sources.",
    )


class TTSVoiceOptions(StrictModel):
    """Voice configuration used by the TTS provider."""

    voice_id: str = Field(description="Provider voice identifier to synthesize with (e.g., Polly voice ID).")
    engine: Literal["standard", "neural"] | None = Field(
        default=None,
        description="Synthesis engine type (if required by the provider).",
    )


TTSProvider = Literal["aws", "azure", "edge"]


class LanguageTTSConfig(StrictModel):
    """Per-language TTS setup: provider and voice options."""

    provider: TTSProvider = Field(
        default="edge",
        description="TTS provider backend.",
    )
    options: TTSVoiceOptions = Field(description="Voice options for this language.")


class AWSProviderAccess(StrictModel):
    """AWS credentials for TTS (Amazon Polly)."""

    access_key_id: SecretStr | None = Field(
        default=None,
        description="AWS Access Key ID. Can be provided via env",
    )
    secret_access_key: SecretStr | None = Field(
        default=None,
        description="AWS Secret Access Key. Can be provided via env",
    )
    region: str | None = Field(
        default=None,
        description="AWS region (e.g., us-east-1) for the TTS service.",
    )


class AzureProviderAccess(StrictModel):
    """Azure credentials for TTS (Cognitive Services Speech)."""

    subscription_key: SecretStr | None = Field(
        default=None,
        description="Azure Cognitive Services subscription key. Can be provided via env",
    )
    region: str | None = Field(
        default=None,
        description="Azure region (e.g., eastus, westeurope) for the TTS service.",
    )


class Text2SpeechSettings(StrictModel):
    """Text-to-Speech configuration."""
    default_provider: TTSProvider = Field(
        default="edge",
        description="Default TTS provider to use if no specific settings are set for a language.",
    )

    languages: dict[str, LanguageTTSConfig] | None = Field(
        default=None,
        description="Optional specific settings for TTS for languages. If not set, defaults will be used.",
    )


class ProviderAccessSettings(StrictModel):
    """Providers credentials."""

    openai: OpenAIProviderAccess | None = None
    aws: AWSProviderAccess | None = None
    azure: AzureProviderAccess | None = None


class MLflowConfig(StrictModel):
    """Configuration for MLflow tracking (optional)."""
    tracking_uri: str | None = Field(
        default=None,
        description="MLflow tracking URI. If None, tracking is disabled.",
    )
    experiment_name: str = Field(
        default="ankify_experiment",
        description="MLflow experiment name.",
    )


NoteType = Literal["forward_and_backward", "forward_only"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANKIFY__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        nested_model_default_partial_update=True,
        cli_parse_args=True,
        cli_prog_name="ankify",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_hide_none_type=True,
        cli_avoid_json=True,
        cli_enforce_required=False,
    )

    mlflow: MLflowConfig = Field(
        default_factory=MLflowConfig,
        description="MLflow configuration.",
    )

    text_input: Path | None = Field(
        default=None,
        description="Path to input text file. If omitted, the text will be read from stdin.",
    )
    table_output: Path | None = Field(
        default=Path("./ankify_vocab.tsv"),
        description="Where to write the TSV vocabulary table. Set to null to skip writing.",
    )
    anki_output: Path | None = Field(
        default=Path("./ankify_deck.apkg"),
        description="Where to write the generated Anki deck file (.apkg). Set to null to skip packaging.",
    )
    anki_deck_name: str = Field(
        default="Ankify",
        description="Name of the generated Anki deck (it's not the file name, it's the deck name within Anki).",
    )

    config: Path | None = Field(
        default=None,
        description=(
            "YAML config file to load. Its values merge at lower priority than CLI/env. "
            "Must not contain a nested 'config' key."
        ),
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (e.g., DEBUG, INFO, WARNING, ERROR).",
    )

    confirm_steps: bool = Field(
        default=True,
        description="If true, interactively confirm key steps before proceeding.",
    )

    language_a: str = Field(description="Target language being studied (e.g., German).")
    language_b: str = Field(description="Known/native language (e.g., English).")

    note_type: NoteType = Field(
        default="forward_and_backward",
        description="Type of Anki notes to create.",
    )

    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM configuration.",
    )

    tts: Text2SpeechSettings = Field(
        default_factory=Text2SpeechSettings,
        description="Text-to-Speech configuration.",
    )

    providers: ProviderAccessSettings = Field(
        default_factory=ProviderAccessSettings,
        description="Provider credentials.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority (high → low): CLI → init kwargs → env → dotenv → YAML → secrets → defaults
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            AnkifyYamlSettingsSource(settings_cls),
            file_secret_settings,
        )


class AnkifyYamlSettingsSource(PydanticBaseSettingsSource):
    """
    Load settings from a YAML file.
    Returns a flat dict matching Settings fields structure; 
    nested dicts are passed through for Pydantic to coerce into nested models.
    """

    def __call__(self) -> dict[str, Any]:
        # Access aggregated values set by previous sources (e.g., CLI/env/dotenv)
        config_path_value = self.current_state.get("config")
        if config_path_value is None:
            return {}

        config_path = Path(str(config_path_value)).expanduser().resolve()
        if not config_path.is_file():
            raise ValueError(f"Config file not found: {config_path}")
        
        text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        
        if 'config' in data:
            raise ValueError(
                "YAML config cannot contain a nested 'config' key. "
                "This option is reserved for the YAML config file itself, "
                "it's only used from the command line via '--config' option."
            )
        
        return data

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # Not used because this source overrides __call__ to return the full mapping.
        # Implemented just to satisfy the abstract interface.
        return None, field_name, False
