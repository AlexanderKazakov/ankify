from pathlib import Path
import shutil
from typing import Iterable

import openai

from ..logging import get_logger, setup_logging
from ..settings import Settings, OpenAIProviderAccess


logger = get_logger("anker.tts.openai.test")
setup_logging("DEBUG")


def _build_openai_client(access: OpenAIProviderAccess | None) -> openai.OpenAI:
    """Create an OpenAI client using configured credentials or defaults."""
    client_kwargs: dict[str, str] = {}
    if access is not None:
        if access.api_key is not None:
            client_kwargs["api_key"] = access.api_key.get_secret_value()
        if access.base_url:
            client_kwargs["base_url"] = access.base_url

    return openai.OpenAI(**client_kwargs)


def _english_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "one, two, three"),
        ("dash", "one - two - three"),
        ("semicolon", "bandage (medical); association (organization)"),
        ("brackets", "bandage (medical)"),
        ("slash", "bandage/medical"),
        ("double_dots", "not only .. but also"),
        ("triple_dots", "not only ... but also"),
        ("ellipsis", "not only … but also"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _german_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "eins, zwei, drei"),
        ("dash", "eins - zwei - drei"),
        ("semicolon", "Verband (medizinisch); Verband (Organisation)"),
        ("brackets", "Verband (medizinisch)"),
        ("slash", "Verband/medizinisch"),
        ("double_dots", "nicht nur .. sondern auch"),
        ("triple_dots", "nicht nur ... sondern auch"),
        ("ellipsis", "nicht nur … sondern auch"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _russian_samples() -> list[tuple[str, str]]:
    return [
        ("comma", "один, два, три"),
        ("dash", "один - два - три"),
        ("semicolon", "бинт (медицинский); ассоциация (организация)"),
        ("brackets", "бинт (медицинский)"),
        ("slash", "бинт/медицинский"),
        ("double_dots", "не только .. но и"),
        ("triple_dots", "не только ... но и"),
        ("ellipsis", "не только … но и"),
        ("xml_chars_ssml", "1 < 2 > 3; >> & a' /b \" c"),
        ("xml_chars_plain", "1 < 2 > 3 >> & a' b \" c"),
    ]


def _iter_languages(settings: Settings) -> Iterable[tuple[str, list[tuple[str, str]]]]:
    # Keep the same language set as the AWS test to compare outputs.
    mapping = {
        "english": _english_samples,
        "german": _german_samples,
        "russian": _russian_samples,
    }
    for lang_key, samples_fn in mapping.items():
        if settings.tts.languages and lang_key in settings.tts.languages:
            # Only run languages that exist in the dev settings, mirroring the AWS test behavior
            yield lang_key, samples_fn()


def _synthesize_to_file(
    client: openai.OpenAI,
    *,
    text: str,
    model: str,
    voice: str,
    out_path: Path,
    instructions: str | None = None,
    speed: float | None = None,
) -> None:
    logger.debug("Calling OpenAI TTS: model=%s voice=%s text=%s", model, voice, text)
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
        instructions=instructions,
        speed=speed,
    ) as response:
        response.stream_to_file(out_path)


def main() -> None:
    # Load OpenAI access from YAML config used for dev testing
    settings = Settings(config=Path("./settings/dev_test.yaml").resolve())
    client = _build_openai_client(settings.providers.openai if settings.providers else None)

    # Where to save results
    out_dir = Path("./tmp/tts_ssml").resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir()

    # Model/voice to test; can be adjusted as desired
    model_name = "gpt-4o-mini-tts"
    voice_name = "alloy"

    for lang_key, samples in _iter_languages(settings):
        logger.info("Testing language=%s model=%s voice=%s", lang_key, model_name, voice_name)
        suffix = {"english": "en", "german": "de", "russian": "ru"}[lang_key]
        instruction = {
            "english": "Say this in English:",
            "german": "Sag das auf Deutsch:",
            "russian": "Скажи это по-русски:",
        }[lang_key]
        for name, text in samples:
            # try:
            out_path = out_dir / f"{name}_{suffix}.mp3"
            _synthesize_to_file(
                client,
                text=text,
                model=model_name,
                voice=voice_name,
                out_path=out_path,
                instructions=instruction,
                speed=1.0,
            )
            logger.info("Saved %s", out_path)
            # except Exception:
            #     logger.exception("OpenAI TTS synthesis failed: lang=%s case=%s", lang_key, name)
            #     continue


if __name__ == "__main__":
    main()


