from pathlib import Path
import uuid

from ..vocab_entry import VocabEntry
from ..settings import (
    Settings,
    Text2SpeechSettings,
    LanguageTTSConfig,
    ProviderAccessSettings,
)
from ..logging import get_logger
from .tts_base import TTSSingleLanguageClient
from .aws_tts import AWSPollySingleLanguageClient


def create_tts_single_language_client(
    config: LanguageTTSConfig,
    providers: ProviderAccessSettings,
) -> TTSSingleLanguageClient:
    if config.provider == "aws":
        return AWSPollySingleLanguageClient(
            access_settings=providers.aws,
            language_settings=config.options,
        )
    else:
        raise ValueError(f"Unsupported TTS provider: {config.provider}")


class TTSManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        config: Text2SpeechSettings = settings.tts
        self.logger = get_logger("anker.tts.manager")
        self.logger.debug("Initializing TTSManager with languages: %s", ", ".join(config.languages.keys()))

        self.tts_clients: dict[str, TTSSingleLanguageClient] = {
            language: create_tts_single_language_client(lang_cfg, settings.providers)
            for language, lang_cfg in config.languages.items()
        }
        self.logger.debug("Initialized TTSManager")

    def synthesize(self, entries: list[VocabEntry], audio_dir: Path) -> None:
        self.logger.info("Starting TTS synthesis for %d vocabulary entries", len(entries))
        # within each language, de-duplicate by text
        by_language = {lang: {} for lang in self.tts_clients}
        for entry in entries:
            by_language[self._check_language_defined(entry.front_language)][entry.front] = None
            by_language[self._check_language_defined(entry.back_language)][entry.back] = None
        
        for lang, lang_entries in by_language.items():
            self.logger.debug("Language '%s' has %d unique texts to synthesize", lang, len(lang_entries))
            if len(lang_entries) != 0:
                self.tts_clients[lang].synthesize(lang_entries)
                # write audio to disk, keep paths instead of bytes
                for text in lang_entries.keys():
                    audio_file_path = audio_dir / f"anker-{uuid.uuid4()}.mp3"
                    audio_file_path.write_bytes(lang_entries[text])
                    lang_entries[text] = audio_file_path
        
        for entry in entries:
            entry.front_audio = by_language[self._check_language_defined(entry.front_language)][entry.front]
            entry.back_audio = by_language[self._check_language_defined(entry.back_language)][entry.back]
        
        self.logger.info("Completed TTS synthesis")

    def _check_language_defined(self, language: str) -> str:
        language = language.lower()
        if language not in self.tts_clients:
            raise ValueError(
                f"Language of the vocabulary entry '{language}' is not defined in the config. "
                f"Defined languages: {', '.join(self.tts_clients.keys())}"
            )
        return language
