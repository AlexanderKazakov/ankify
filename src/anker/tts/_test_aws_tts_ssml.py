from pathlib import Path
import shutil
from typing import Iterable

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..logging import get_logger, setup_logging
from ..settings import Settings, AWSProviderAccess, TTSVoiceOptions
from .aws_tts import AWSPollySingleLanguageClient


logger = get_logger("anker.tts.aws.ssml_test")
setup_logging("DEBUG")


def _build_polly_client(access: AWSProviderAccess | None) -> BaseClient:
    """Create a Polly client. If explicit credentials are provided, use them; otherwise fallback to default AWS resolution chain."""
    session_kwargs: dict[str, str] = {}
    if access is not None:
        if access.access_key_id is not None and access.secret_access_key is not None:
            session_kwargs["aws_access_key_id"] = access.access_key_id.get_secret_value()
            session_kwargs["aws_secret_access_key"] = access.secret_access_key.get_secret_value()
        if access.region:
            session_kwargs["region_name"] = access.region

    session = boto3.Session(**session_kwargs)
    return session.client("polly")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((BotoCoreError, ClientError)),
)
def _synthesize(
    client: BaseClient,
    *,
    text: str,
    is_ssml: bool,
    voice: TTSVoiceOptions,
) -> bytes:
    params: dict[str, str] = {
        "Text": text,
        "OutputFormat": "mp3",
        "VoiceId": voice.voice_id,
        "Engine": voice.engine,
    }
    if is_ssml:
        params["TextType"] = "ssml"

    logger.debug("Calling Polly synthesize_speech:\n%s", params)
    response = client.synthesize_speech(**params)
    if "AudioStream" not in response or response["AudioStream"] is None:
        logger.error("Polly response missing AudioStream", response)
        raise RuntimeError("Polly response did not contain AudioStream")

    with closing(response["AudioStream"]) as stream:
        return stream.read()


def _english_samples() -> dict[str, tuple[str, bool]]:
    return {
        "semicolon_plain": ("bandage (medical); association (organization)", False),
        "semicolon_ssml_medium": ("<speak>bandage (medical)<break strength='medium'/> association (organization)</speak>", True),
        "semicolon_ssml_strong": ("<speak>bandage (medical)<break strength='strong'/> association (organization)</speak>", True),
        "brackets_plain": ("bandage (medical)", False),
        # "brackets_plain_wo": ("bandage medical", False),
        "slash_plain": ("bandage/medical", False),
        "slash_ssml_medium": ("<speak>bandage<break strength='medium'/>medical</speak>", True),
        "double_dots_plain": ("not only .. but also", False),
        "triple_dots_plain": ("not only ... but also", False),
        "ellipsis_plain": ("not only … but also", False),
    }


def _german_samples() -> dict[str, tuple[str, bool]]:
    return {
        "semicolon_plain": ("Verband (medizinisch); Verband (Organisation)", False),
        "semicolon_ssml_medium": ("<speak>Verband (medizinisch)<break strength='medium'/> Verband (Organisation)</speak>", True),
        "semicolon_ssml_strong": ("<speak>Verband (medizinisch)<break strength='strong'/> Verband (Organisation)</speak>", True),
        "brackets_plain": ("Verband (medizinisch)", False),
        # "brackets_plain_wo": ("Verband medizinisch", False),
        "slash_plain": ("Verband/medizinisch", False),
        "slash_ssml_medium": ("<speak>Verband<break strength='medium'/>medizinisch</speak>", True),
        "double_dots_plain": ("nicht nur .. sondern auch", False),
        "triple_dots_plain": ("nicht nur ... sondern auch", False),
        "ellipsis_plain": ("nicht nur … sondern auch", False),
    }


def _russian_samples() -> dict[str, tuple[str, bool]]:
    return {
        "semicolon_plain": ("бинт (медицинский); ассоциация (организация)", False),
        "semicolon_ssml_medium": ("<speak>бинт (медицинский)<break strength='medium'/> ассоциация (организация)</speak>", True),
        "semicolon_ssml_strong": ("<speak>бинт (медицинский)<break strength='strong'/> ассоциация (организация)</speak>", True),
        "brackets_plain": ("бинт (медицинский)", False),
        # "brackets_plain_wo": ("бинт медицинский", False),
        "slash_plain": ("бинт/медицинский", False),
        "slash_ssml_medium": ("<speak>бинт<break strength='medium'/>медицинский</speak>", True),
        "double_dots_plain": ("не только .. но и", False),
        "triple_dots_plain": ("не только ... но и", False),
        "ellipsis_plain": ("не только … но и", False),
    }


def _iter_languages(settings: Settings) -> Iterable[tuple[str, TTSVoiceOptions, dict[str, tuple[str, bool]]]]:
    mapping = {
        "english": _english_samples,
        "german": _german_samples,
        "russian": _russian_samples,
    }
    for lang_key, samples_fn in mapping.items():
        if lang_key in settings.tts.languages:
            voice_opts = settings.tts.languages[lang_key].options
            yield lang_key, voice_opts, samples_fn()


def main1() -> None:
    # Load voices and AWS access from YAML config used for dev testing
    settings = Settings(config=Path("./settings/dev_test.yaml").resolve())

    client = _build_polly_client(settings.providers.aws)

    out_dir = Path("./tmp/tts_ssml").resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir()

    for lang_key, voice_opts, samples in _iter_languages(settings):
        logger.info("Testing language=%s voice=%s engine=%s", lang_key, voice_opts.voice_id, voice_opts.engine)
        for case_name, (text, is_ssml) in samples.items():
            try:
                audio = _synthesize(client, text=text, is_ssml=is_ssml, voice=voice_opts)
            except Exception as e:
                logger.exception("Synthesis failed: lang=%s voice=%s case=%s", lang_key, voice_opts.voice_id, case_name)
                continue

            filename = f"{lang_key}-{voice_opts.voice_id}-{voice_opts.engine}-{case_name}.mp3"
            path = out_dir / filename
            path.write_bytes(audio)
            logger.info("Saved %s", path)



def main2() -> None:
    # Load voices and AWS access from YAML config used for dev testing
    settings = Settings(config=Path("./settings/dev_test.yaml").resolve())

    out_dir = Path("./tmp/tts_ssml").resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir()

    aws_client = AWSPollySingleLanguageClient(
        access_settings=settings.providers.aws,
        language_settings=settings.tts.languages["english"].options,
    )
    for name, text in [
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
    ]:
        audio = aws_client._synthesize_single(text)
        path = out_dir / f"{name}_en.mp3"
        path.write_bytes(audio)
        logger.info("Saved %s", path)

    aws_client = AWSPollySingleLanguageClient(
        access_settings=settings.providers.aws,
        language_settings=settings.tts.languages["german"].options,
    )
    for name, text in [
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
    ]:
        audio = aws_client._synthesize_single(text)
        path = out_dir / f"{name}_de.mp3"
        path.write_bytes(audio)
        logger.info("Saved %s", path)

    aws_client = AWSPollySingleLanguageClient(
        access_settings=settings.providers.aws,
        language_settings=settings.tts.languages["russian"].options,
    )
    for name, text in [
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
    ]:
        audio = aws_client._synthesize_single(text)
        path = out_dir / f"{name}_ru.mp3"
        path.write_bytes(audio)
        logger.info("Saved %s", path)




if __name__ == "__main__":
    # main1()
    main2()


