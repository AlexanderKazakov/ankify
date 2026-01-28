from pathlib import Path
import uuid

from .default_tts_configuration import DefaultTTSConfigurator
from ..vocab_entry import VocabEntry
from ..settings import (
    Text2SpeechSettings,
    LanguageTTSConfig,
    ProviderAccessSettings,
)
from ..logging import get_logger
from .tts_base import TTSSingleLanguageClient
from .tts_cost_tracker import MultiProviderCostTracker


def create_tts_single_language_client(
    config: LanguageTTSConfig,
    providers: ProviderAccessSettings,
) -> tuple[TTSSingleLanguageClient, str]:
    """
    Create a TTS client for the given config.
    Returns a tuple of (client, provider_name).
    
    TTS provider modules are imported lazily to allow installations
    with only a subset of TTS dependencies.
    """
    if config.provider == "aws":
        try:
            from .aws_tts import AWSPollySingleLanguageClient
        except ImportError as e:
            raise ImportError(
                "AWS TTS provider requires 'boto3'. "
                "Install with: pip install ankify[tts-aws]"
            ) from e
        return (
            AWSPollySingleLanguageClient(
                access_settings=providers.aws,
                language_settings=config.options,
            ),
            "aws",
        )
    if config.provider == "azure":
        try:
            from .azure_tts import AzureTTSSingleLanguageClient
        except ImportError as e:
            raise ImportError(
                "Azure TTS provider requires 'azure-cognitiveservices-speech'. "
                "Install with: pip install ankify[tts-azure]"
            ) from e
        return (
            AzureTTSSingleLanguageClient(
                access_settings=providers.azure,
                language_settings=config.options,
            ),
            "azure",
        )
    if config.provider == "edge":
        try:
            from .edge_tts import EdgeTTSSingleLanguageClient
        except ImportError as e:
            raise ImportError(
                "Edge TTS provider requires 'edge-tts'. "
                "Install with: pip install ankify[tts-edge]"
            ) from e
        return (
            EdgeTTSSingleLanguageClient(
                language_settings=config.options,
            ),
            "edge",
        )
    else:
        raise ValueError(f"Unsupported TTS provider: {config.provider}")


class TTSManager:
    def __init__(
        self,
        tts_settings: Text2SpeechSettings,
        provider_settings: ProviderAccessSettings,
    ) -> None:

        self.logger = get_logger("ankify.tts.manager")
        self.logger.debug("Initializing TTSManager...")
        self.provider_settings = provider_settings

        # to instantiate a default language client if a language is not explicitly configured in settings
        self.defaults_configurator = DefaultTTSConfigurator(default_provider=tts_settings.default_provider)

        self.tts_clients: dict[str, TTSSingleLanguageClient] = {}
        self.client_providers: dict[str, str] = {}  # Track which provider each client uses
        if tts_settings.languages is not None:
            for language, lang_cfg in tts_settings.languages.items():
                client, provider = create_tts_single_language_client(lang_cfg, provider_settings)
                self.tts_clients[language] = client
                self.client_providers[language] = provider
        
        self.logger.debug("Initialized TTSManager")

    def synthesize(self, entries: list[VocabEntry], audio_dir: Path) -> None:
        self.logger.info("Starting TTS synthesis for %d vocabulary entries", len(entries))
        
        # Track costs for this synthesis session (supports multiple providers)
        session_cost_tracker = MultiProviderCostTracker()
        
        # within each language, de-duplicate by text
        by_language: dict[str, dict[str, bytes | Path | None]] = {}
        for entry in entries:
            front_lang = self._ensure_client_for_language(entry.front_language)
            back_lang = self._ensure_client_for_language(entry.back_language)

            if front_lang not in by_language:
                by_language[front_lang] = {}
            if back_lang not in by_language:
                by_language[back_lang] = {}

            by_language[front_lang][entry.front] = None
            by_language[back_lang][entry.back] = None
        
        for lang, lang_entries in by_language.items():
            self.logger.debug("Language '%s' has %d unique texts to synthesize", lang, len(lang_entries))
            if len(lang_entries) != 0:
                # Get the cost tracker for this language's provider
                provider = self.client_providers[lang]
                cost_tracker = session_cost_tracker.get_tracker(provider)
                self.tts_clients[lang].synthesize(lang_entries, language=lang, cost_tracker=cost_tracker)
                # write audio to disk, keep paths instead of bytes
                for text in lang_entries.keys():
                    audio_file_path = audio_dir / f"ankify-{uuid.uuid4()}.mp3"
                    audio_file_path.write_bytes(lang_entries[text])
                    lang_entries[text] = audio_file_path
        
        for entry in entries:
            # We use _ensure_client_for_language again just to get the normalized key,
            # but we know it's there.
            front_lang = self._ensure_client_for_language(entry.front_language)
            back_lang = self._ensure_client_for_language(entry.back_language)
            entry.front_audio = by_language[front_lang][entry.front]
            entry.back_audio = by_language[back_lang][entry.back]
        
        # Log cost summaries for all providers that were used
        session_cost_tracker.log_summary()

        self.logger.info("Completed TTS synthesis")

    def _ensure_client_for_language(self, language: str) -> str:
        language = language.lower()
        if language in self.tts_clients:
            return language
        
        self.logger.info("Language '%s' not configured; loading defaults", language)
        config = self.defaults_configurator.get_config(language)
        
        # Update the clients map
        client, provider = create_tts_single_language_client(config, self.provider_settings)
        self.tts_clients[language] = client
        self.client_providers[language] = provider
        return language
