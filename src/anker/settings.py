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
    model: str = Field(default="gpt-5")
    # Path to the prompt or prompt template (".j2")
    prompt_template: Path = Field(default=Path("./settings/prompts/prompt_template.md.j2"))
    # Optional file with additional custom instructions to be inlined into the prompt
    custom_instructions: Path | None = Field(default=None)
    # Optional directory with few-shot examples to be inlined into the prompt. 
    # Each example consists of a pair of files with the same stem: 
    # "N.txt" (input) and "N.tsv" (output).
    few_shot_examples: Path | None = Field(default=None)


class OpenAIProviderAccess(StrictModel):
    api_key: SecretStr | None = Field(default=None)


class LLMProviderAccessSettings(StrictModel):
    openai: OpenAIProviderAccess | None = None


class LLMConfig(StrictModel):
    provider: Literal["openai"] = Field(default="openai")
    options: LLMOptions = Field(default_factory=LLMOptions)
    providers: LLMProviderAccessSettings | None = None


class TTSVoiceOptions(StrictModel):
    voice_id: str
    engine: Literal["standard", "neural"] = Field(default="neural")


class LanguageTTSConfig(StrictModel):
    provider: Literal["aws"] = Field(default="aws")
    options: TTSVoiceOptions


class AWSProviderAccess(StrictModel):
    access_key_id: SecretStr | None = Field(default=None)
    secret_access_key: SecretStr | None = Field(default=None)
    region: str | None = Field(default=None)


class TTSAggregatedProviderAccessSettings(StrictModel):
    aws: AWSProviderAccess | None = None


class Text2SpeechSettings(StrictModel):
    languages: dict[str, LanguageTTSConfig] = Field(default_factory=dict)
    providers: TTSAggregatedProviderAccessSettings | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANKER__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        nested_model_default_partial_update=True,
        cli_parse_args=True,
        cli_prog_name="anker",
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_hide_none_type=True,
        cli_avoid_json=True,
        cli_enforce_required=False,
    )

    # Paths
    text_input: Path | None = None
    table_output: Path | None = Path("./anker_vocab.tsv")
    anki_output: Path | None = Path("./anker_deck.apkg")

    # Optional path to a YAML config file (positional CLI arg `config`)
    # If provided, values from this file will be merged at lower priority than CLI/env.
    # Note that this yaml should not contain a nested `config` key.
    config: Path | None = None

    # Verbosity
    log_level: str = "INFO"

    # Whether to confirm steps before they are executed
    confirm_steps: bool = True

    # The language being studied
    language_a: str
    # The known/native language
    language_b: str

    # The type of notes to create. Should be consistent with the LLM prompt.
    note_type: Literal["forward_and_backward", "forward_only"] = Field(default="forward_and_backward")

    # LLM configuration
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Text-to-Speech configuration
    tts: Text2SpeechSettings = Field(default_factory=Text2SpeechSettings)

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
            AnkerYamlSettingsSource(settings_cls),
            file_secret_settings,
        )


class AnkerYamlSettingsSource(PydanticBaseSettingsSource):
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


