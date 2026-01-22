import json
from importlib import resources

from ..settings import LanguageTTSConfig, TTSVoiceOptions, TTSProvider
from ..logging import get_logger

logger = get_logger(__name__)


class DefaultTTSConfigurator:
    def __init__(self, default_provider: TTSProvider) -> None:
        self.default_provider = default_provider
        self.defaults = None

    def _load_defaults(self, provider: str) -> dict[str, str | dict[str, str]]:
        filename = f"tts_defaults_{provider}.json"
        content = resources.files("ankify.resources.tts").joinpath(filename).read_text(encoding="utf-8")
        defaults: dict[str, str | dict[str, str]] = json.loads(content)
        logger.debug("Loaded %s default voice codes for provider '%s'.", len(defaults), provider)

        aliases_content = resources.files("ankify.resources").joinpath("language_aliases.json").read_text(encoding="utf-8")
        aliases: dict[str, str] = json.loads(aliases_content)
        added_aliases = {}
        for alias, target in aliases.items():
            if alias not in defaults and target in defaults:
                added_aliases[alias] = defaults[target]

        logger.debug("Loaded %s language aliases for provider '%s'.", len(added_aliases), provider)
        defaults.update(added_aliases)
        logger.debug("Total %s default voice codes for provider '%s'.", len(defaults), provider)
        return defaults

    def get_config(self, language: str) -> LanguageTTSConfig:
        if self.defaults is None:
            self.defaults = self._load_defaults(self.default_provider)

        language = language.lower()
        if language not in self.defaults:
            raise ValueError(
                f"No default voice exists for language '{language}' (provider: {self.default_provider}). "
                f"Make sure you are using a valid language code. "
                f"Available language codes: {sorted(self.defaults.keys())}"
            )
        
        value = self.defaults[language]
        options = TTSVoiceOptions(**value)
        return LanguageTTSConfig(
            provider=self.default_provider,
            options=options
        )
