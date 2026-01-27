import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, TYPE_CHECKING
from xml.sax.saxutils import escape as xml_escape

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..logging import get_logger
from ..settings import TTSVoiceOptions
from .tts_base import TTSSingleLanguageClient

if TYPE_CHECKING:
    from .tts_cost_tracker import TTSCostTracker


class EdgeTTSSingleLanguageClient(TTSSingleLanguageClient):
    ssml_mapping = [
        ("/", "<break strength='medium'/>", "__ankify_sentinel_slash__"),
        (";", "<break strength='strong'/>", "__ankify_sentinel_semicolon__"),
    ]

    @staticmethod
    def possibly_preprocess_text_into_ssml(text: str) -> str:
        """
        Semicolons are replaced with strong breaks, slashes are replaced with medium breaks.
        Everything else is left as is, since it works fine as plain text.
        If there are no characters that need to be replaced, the text is returned as is.
        If there are characters that need to be replaced, the text is returned as SSML, XML-escaped.
        """
        if not any(c in text for c, _, _ in EdgeTTSSingleLanguageClient.ssml_mapping):
            return text

        for char, _, sentinel in EdgeTTSSingleLanguageClient.ssml_mapping:
            text = text.replace(char, sentinel)

        text = xml_escape(text)

        for _, replacement, sentinel in EdgeTTSSingleLanguageClient.ssml_mapping:
            text = text.replace(sentinel, replacement)

        return f"<speak>{text}</speak>"

    def __init__(self, language_settings: TTSVoiceOptions) -> None:
        self.logger = get_logger("ankify.tts.edge")
        self.logger.debug(
            "Initializing Edge TTS client for voice id '%s'", language_settings.voice_id
        )
        self._language_settings = language_settings

    def synthesize(
        self,
        entities: dict[str, bytes | None],
        language: str,
        cost_tracker: "TTSCostTracker | None" = None,
    ) -> None:
        self.logger.info(
            "Synthesizing speech for %d entities, voice id '%s'",
            len(entities),
            self._language_settings.voice_id,
        )

        for text in entities:
            entities[text] = self._synthesize_single(text)
            if cost_tracker:
                cost_tracker.track_usage(text, "free", language)

    def _run_coroutine(self, coro_factory: Callable[[], Awaitable[bytes]]) -> bytes:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_factory())

        self.logger.debug("Running Edge TTS coroutine in a dedicated event loop thread")

        def runner() -> bytes:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro_factory())
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(runner).result()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    def _synthesize_single(self, text: str) -> bytes:
        prepared_text = self.possibly_preprocess_text_into_ssml(text)
        return self._run_coroutine(lambda: self._synthesize_single_async(prepared_text))

    async def _synthesize_single_async(self, text: str) -> bytes:
        # Lazy import to avoid asyncio conflicts at module load time in FastMCP cloud
        import edge_tts
        
        self.logger.debug(
            "Calling Edge TTS: voice=%s text=%s", self._language_settings.voice_id, text
        )
        communicate = edge_tts.Communicate(text, self._language_settings.voice_id)
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            self.logger.error(
                "Edge TTS returned no audio. voice_id='%s' text='%s'",
                self._language_settings.voice_id,
                text,
            )
            raise RuntimeError("Edge TTS response did not contain audio data")

        return b"".join(audio_chunks)
