from typing import Literal

from pydantic import BaseModel, Field, SecretStr, ConfigDict


class StrictModel(BaseModel):
    """Base for nested config models; forbids unknown fields to catch YAML typos."""

    model_config = ConfigDict(extra="forbid")


class TTSVoiceOptions(StrictModel):
    """Voice configuration used by the TTS provider."""

    voice_id: str = Field(
        description="Provider voice identifier to synthesize with (e.g., Polly voice ID)."
    )
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
    region: str = Field(
        default="eu-central-1",
        description="AWS region (e.g., eu-central-1) for the TTS service.",
    )


class AzureProviderAccess(StrictModel):
    """Azure credentials for TTS (Cognitive Services Speech)."""

    subscription_key: SecretStr | None = Field(
        default=None,
        description="Azure Cognitive Services subscription key. Can be provided via env",
    )
    region: str = Field(
        default="westeurope",
        description="Azure region (e.g., westeurope) for the TTS service.",
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

    aws: AWSProviderAccess | None = None
    azure: AzureProviderAccess | None = None


NoteType = Literal["basic", "basic_and_reversed"]

ANKIFY_NOTE_TYPE_MODEL_NAME: dict[NoteType, str] = {
    "basic": "Ankify Basic",
    "basic_and_reversed": "Ankify Basic & Reversed",
}
