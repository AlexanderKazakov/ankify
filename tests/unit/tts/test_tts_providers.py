import unicodedata
from decimal import Decimal
from difflib import SequenceMatcher

import pytest

from ankify.settings import ProviderAccessSettings
from ankify.tts.default_tts_configuration import DefaultTTSConfigurator
from ankify.tts.tts_cost_tracker import (
    AWSPollyCostTracker,
    AzureTTSCostTracker,
    EdgeTTSCostTracker,
)
from ankify.tts.tts_manager import create_tts_single_language_client
from ankify.tts.tts_text_preprocessor import has_cjk

from .stt_helper import AzureSTTHelper


TEST_CASES: list[tuple[str, str, str, str]] = [
    ### Simple text
    ("simple", "english", "Hello, how are you?", "en-US"),
    ("simple", "german", "Guten Tag, wie geht es Ihnen?", "de-DE"),
    ("simple", "russian", "Здравствуйте, как дела?", "ru-RU"),
    ("simple", "french", "Bonjour, comment allez-vous?", "fr-FR"),
    ("simple", "spanish", "Hola, ¿cómo estás?", "es-ES"),
    ("simple", "italian", "Buongiorno, come sta?", "it-IT"),
    ("simple", "portuguese", "Olá, como vai você?", "pt-BR"),
    ("simple", "japanese", "こんにちは、お元気ですか", "ja-JP"),
    ("simple", "korean", "안녕하세요", "ko-KR"),
    ("simple", "chinese", "你好，你好吗", "zh-CN"),
    ("simple", "hindi", "नमस्ते, आप कैसे हैं", "hi-IN"),
    ("simple", "arabic", "مرحبا، كيف حالك", "ar-SA"),
    ("simple", "dutch", "Hallo, hoe gaat het?", "nl-NL"),
    ("simple", "polish", "Dzień dobry, jak się masz?", "pl-PL"),
    ("simple", "turkish", "Merhaba, nasılsınız?", "tr-TR"),
    ### Text with special characters
    ("special_chars", "english", "because/due to; for / as", "en-US"),
    ("special_chars", "german", "deshalb/wegen; da / weil", "de-DE"),
    ("special_chars", "russian", "потому что/из-за; ведь / так как", "ru-RU"),
    ("special_chars", "french", "parce que/à cause de; pour / comme", "fr-FR"),
    ("special_chars", "spanish", "porque/debido a; para / como", "es-ES"),
    ("special_chars", "italian", "perché/a causa di; per / come", "it-IT"),
    ("special_chars", "portuguese", "porque/devido a; para / como", "pt-BR"),
    ("special_chars", "japanese", "から/ので; のために / として", "ja-JP"),
    ("special_chars", "korean", "왜냐하면/때문에; 를 위해 / 로서", "ko-KR"),
    ("special_chars", "chinese", "因为/由于; 为了 / 作为", "zh-CN"),
    ("special_chars", "hindi", "क्योंकि/के कारण; के लिए / जैसा", "hi-IN"),
    ("special_chars", "arabic", "لأن/بسبب; من أجل / كما", "ar-SA"),
    ("special_chars", "dutch", "omdat/vanwege; voor / als", "nl-NL"),
    ("special_chars", "polish", "ponieważ/z powodu; dla / jako", "pl-PL"),
    ("special_chars", "turkish", "çünkü/nedeniyle; için / olarak", "tr-TR"),
]

PROVIDERS = [
    "aws",
    "azure",
    "edge",
]
TRACKER_BY_PROVIDER = {
    "aws": AWSPollyCostTracker,
    "azure": AzureTTSCostTracker,
    "edge": EdgeTTSCostTracker,
}


def _katakana_to_hiragana(text: str) -> str:
    """Convert katakana to hiragana so STT script variants don't penalise similarity."""
    result: list[str] = []
    for ch in text:
        cp = ord(ch)
        # Katakana U+30A1..U+30F6 → Hiragana U+3041..U+3096 (offset 0x60)
        if 0x30A1 <= cp <= 0x30F6:
            result.append(chr(cp - 0x60))
        else:
            result.append(ch)
    return "".join(result)


def _normalize_text(text: str) -> str:
    # NFKC: fullwidth → halfwidth, compatibility decompositions
    normalized = unicodedata.normalize("NFKC", text.lower())
    if has_cjk(normalized):
        # CJK: strip non-alnum (no word-separating spaces), unify kana scripts
        stripped = "".join(ch for ch in normalized if ch.isalnum())
        return _katakana_to_hiragana(stripped)
    cleaned = "".join(ch if ch.isalnum() else " " for ch in normalized)
    return " ".join(cleaned.split())


def _similarity_ratio(expected: str, actual: str) -> float:
    return SequenceMatcher(
        None, _normalize_text(expected), _normalize_text(actual)
    ).ratio()


def _provider_access(
    provider: str, request: pytest.FixtureRequest
) -> ProviderAccessSettings:
    if provider == "aws":
        return ProviderAccessSettings(aws=request.getfixturevalue("aws_access"))
    if provider == "azure":
        return ProviderAccessSettings(azure=request.getfixturevalue("azure_access"))
    return ProviderAccessSettings()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "test_case", TEST_CASES, ids=["_".join(case[:2]) for case in TEST_CASES]
)
def test_tts_provider_audio_transcribes_to_expected_text(
    provider,
    test_case,
    request,
    azure_access,
):
    category, language, text, transcribe_language_code = test_case
    provider_access = _provider_access(provider, request)
    AzureSTTHelper.require_mp3_support()

    config = DefaultTTSConfigurator(default_provider=provider).get_config(language)
    client, resolved_provider = create_tts_single_language_client(
        config, provider_access
    )

    assert resolved_provider == provider

    entities = {text: None}
    client.synthesize(entities, language, None)
    audio = entities[text]
    assert audio is not None
    assert isinstance(audio, bytes)
    assert len(audio) > 100

    recognized_text = AzureSTTHelper.transcribe(
        audio_bytes=audio,
        language_code=transcribe_language_code,
        azure_access=azure_access,
    )
    ratio = _similarity_ratio(text, recognized_text)

    critical_ratio = 0.8
    if has_cjk(text):
        critical_ratio = 0.7

    ### For debugging
    # if ratio < critical_ratio:
    #     from pathlib import Path
    #     Path(f"./tmp/tts_tests/{provider}_{language}_{category}.mp3").write_bytes(audio)

    assert ratio >= critical_ratio, (
        f"TTS mismatch: {provider} {language}: `{text}` -> `{recognized_text}` (ratio={ratio:.3f})"
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_cost_tracker_records_usage(provider, request):
    provider_access = _provider_access(provider, request)
    config = DefaultTTSConfigurator(default_provider=provider).get_config("english")
    client, _ = create_tts_single_language_client(config, provider_access)
    tracker = TRACKER_BY_PROVIDER[provider]()

    entities = {"Hello world": None}
    client.synthesize(entities, "english", tracker)

    total_chars = sum(u.chars for u in tracker._usage.values())
    total_cost = sum(u.cost for u in tracker._usage.values())

    assert total_chars > 0
    if provider == "edge":
        assert total_cost == Decimal("0.00")
    else:
        assert total_cost > Decimal("0.00")
