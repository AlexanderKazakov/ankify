import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from contextlib import closing
from xml.sax.saxutils import escape as xml_escape

from ..logging import get_logger
from ..settings import TTSVoiceOptions, AWSProviderAccess
from .tts_base import TTSSingleLanguageClient


class AWSPollySingleLanguageClient(TTSSingleLanguageClient):
    ssml_mapping = [
        ("/", "<break strength='medium'/>", "__anker_sentinel_slash__"),
        (";", "<break strength='strong'/>", "__anker_sentinel_semicolon__"),
    ]

    @staticmethod
    def possibly_preprocess_text_into_ssml(text: str) -> dict:
        """
        Semicolons are replaced with strong breaks, slashes are replaced with medium breaks.
        Everything else is left as is, since it works fine as plain text.
        If there are no characters that need to be replaced, the text is returned as is.
        If there are characters that need to be replaced, the text is returned as SSML, XML-escaped.
        """
        if not any(c in text for c, _, _ in AWSPollySingleLanguageClient.ssml_mapping):
            return {
                "Text": text,
            }

        for char, replacement, sentinel in AWSPollySingleLanguageClient.ssml_mapping:
            text = text.replace(char, sentinel)
        
        text = xml_escape(text)
        
        for char, replacement, sentinel in AWSPollySingleLanguageClient.ssml_mapping:
            text = text.replace(sentinel, replacement)
                
        return {
            "Text": f"<speak>{text}</speak>",
            "TextType": "ssml",
        }

    def __init__(self, access_settings: AWSProviderAccess, language_settings: TTSVoiceOptions):
        self.logger = get_logger("anker.tts.aws")
        self.logger.debug(
            "Initializing AWS Polly client for voice id '%s' and engine '%s'", 
            language_settings.voice_id, language_settings.engine,
        )

        session_kwargs = {
            "aws_access_key_id": access_settings.access_key_id.get_secret_value(),
            "aws_secret_access_key": access_settings.secret_access_key.get_secret_value(),
            "region_name": access_settings.region,
        }
        session = boto3.Session(**session_kwargs)
        self._client: BaseClient = session.client("polly")

        self._language_settings = language_settings
    
    def synthesize(self, entities: dict[str, bytes | None]) -> None:
        self.logger.info(
            "Synthesizing speech for %d entities, voice id '%s', engine '%s'",
            len(entities), self._language_settings.voice_id, self._language_settings.engine,
        )

        # TODO: batching
        for text in entities:
            entities[text] = self._synthesize_single(text)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type((BotoCoreError, ClientError)),
    )
    def _synthesize_single(self, text: str) -> bytes:
        params = self.possibly_preprocess_text_into_ssml(text)
        response = self._client.synthesize_speech(
            **params,
            OutputFormat="mp3",
            VoiceId=self._language_settings.voice_id,
            Engine=self._language_settings.engine,
        )

        if "AudioStream" not in response or response["AudioStream"] is None:
            self.logger.error(
                "Polly response missing AudioStream. voice_id='%s' engine='%s' text='%s'",
                self._language_settings.voice_id, self._language_settings.engine, text,
            )
            raise RuntimeError("Polly response did not contain AudioStream")

        with closing(response["AudioStream"]) as stream:
            audio_bytes = stream.read()

        return audio_bytes

