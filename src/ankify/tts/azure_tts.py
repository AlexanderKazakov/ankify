import azure.cognitiveservices.speech as speechsdk
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from xml.sax.saxutils import escape as xml_escape

from ..logging import get_logger
from ..settings import TTSVoiceOptions, AzureProviderAccess
from .tts_base import TTSSingleLanguageClient
from .tts_cost_tracker import TTSCostTracker


class AzureTTSSingleLanguageClient(TTSSingleLanguageClient):
    """Azure Cognitive Services Speech TTS client for a single language."""

    ssml_mapping = [
        ("/", "<break strength='medium'/>", "__ankify_sentinel_slash__"),
        (";", "<break strength='strong'/>", "__ankify_sentinel_semicolon__"),
    ]

    @staticmethod
    def possibly_preprocess_text_into_ssml(text: str, voice_id: str) -> tuple[str, bool]:
        """
        Semicolons are replaced with strong breaks, slashes are replaced with medium breaks.
        Everything else is left as is, since it works fine as plain text.
        If there are no characters that need to be replaced, the text is returned as is.
        If there are characters that need to be replaced, the text is returned as SSML, XML-escaped.
        
        Returns a tuple of (text, is_ssml).
        """
        if not any(c in text for c, _, _ in AzureTTSSingleLanguageClient.ssml_mapping):
            return text, False

        for char, _, sentinel in AzureTTSSingleLanguageClient.ssml_mapping:
            text = text.replace(char, sentinel)

        text = xml_escape(text)

        for _, replacement, sentinel in AzureTTSSingleLanguageClient.ssml_mapping:
            text = text.replace(sentinel, replacement)

        # Azure requires specific SSML format with voice element
        ssml = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><voice name="{voice_id}">{text}</voice></speak>'
        return ssml, True

    def __init__(self, access_settings: AzureProviderAccess, language_settings: TTSVoiceOptions):
        self.logger = get_logger("ankify.tts.azure")
        self.logger.debug(
            "Initializing Azure TTS client for voice id '%s'",
            language_settings.voice_id,
        )

        speech_config = speechsdk.SpeechConfig(
            subscription=access_settings.subscription_key.get_secret_value(),
            region=access_settings.region,
        )
        # Set the output format to MP3
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        self._speech_config = speech_config
        self._language_settings = language_settings

    def synthesize(
        self,
        entities: dict[str, bytes | None],
        language: str,
        cost_tracker: TTSCostTracker | None = None,
    ) -> None:
        self.logger.info(
            "Synthesizing speech for %d entities, voice id '%s'",
            len(entities),
            self._language_settings.voice_id,
        )

        for text in entities:
            entities[text] = self._synthesize_single(text, language, cost_tracker)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type((RuntimeError,)),
    )
    def _synthesize_single(self, text: str, language: str, cost_tracker: TTSCostTracker | None) -> bytes:
        voice_id = self._language_settings.voice_id
        prepared_text, is_ssml = self.possibly_preprocess_text_into_ssml(text, voice_id)

        # Set the voice name on the config (needed for plain text synthesis)
        self._speech_config.speech_synthesis_voice_name = voice_id

        # Create a new synthesizer per call (thread-safe approach)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self._speech_config,
            audio_config=None,  # We want to get the audio data, not play it
        )

        self.logger.debug(
            "Calling Azure TTS: voice=%s is_ssml=%s text=%s",
            voice_id, is_ssml, text[:50] + "..." if len(text) > 50 else text,
        )

        if is_ssml:
            result = synthesizer.speak_ssml_async(prepared_text).get()
        else:
            result = synthesizer.speak_text_async(prepared_text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            if cost_tracker:
                # Track original text length for cost calculation
                cost_tracker.track_usage(text, "neural", language)

            return result.audio_data

        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            self.logger.error(
                "Azure TTS synthesis canceled. reason=%s error_details=%s voice_id='%s' text='%s'",
                cancellation.reason,
                cancellation.error_details,
                voice_id,
                text,
            )
            # Check if it's a connection/service error that should be retried
            if cancellation.reason == speechsdk.CancellationReason.Error:
                raise RuntimeError(
                    f"Azure TTS synthesis failed: {cancellation.error_details}"
                )
            raise RuntimeError(f"Azure TTS synthesis canceled: {cancellation.reason}")

        else:
            self.logger.error(
                "Azure TTS returned unexpected result. reason=%s voice_id='%s' text='%s'",
                result.reason,
                voice_id,
                text,
            )
            raise RuntimeError(f"Azure TTS unexpected result: {result.reason}")
