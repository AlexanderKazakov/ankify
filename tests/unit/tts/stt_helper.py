import threading
from functools import cache
from platform import system

import azure.cognitiveservices.speech as speechsdk
import pytest
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ankify.settings import AzureProviderAccess

_CONTINUOUS_TIMEOUT_S = 10


@cache
def _azure_speech_mp3_support_error() -> str | None:
    speech_config = speechsdk.SpeechConfig(
        subscription="dummy",
        region="westeurope",
    )
    compressed_format = speechsdk.audio.AudioStreamFormat(
        compressed_stream_format=speechsdk.audio.AudioStreamContainerFormat.MP3
    )
    stream = speechsdk.audio.PushAudioInputStream(compressed_format)
    stream.close()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    try:
        # Recognizer construction loads the native MP3 codec pipeline before
        # any Azure network request, so dummy credentials are enough here.
        speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )
    except RuntimeError as exc:
        message = str(exc)
        if "SPXERR_GSTREAMER_NOT_FOUND_ERROR" in message or "0x29" in message:
            return message
        raise

    return None


def _gstreamer_failure_help() -> str:
    linux_install = (
        "Linux install command:\n"
        "  sudo apt-get install -y libgstreamer1.0-0 "
        "gstreamer1.0-plugins-base gstreamer1.0-plugins-good "
        "gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly"
    )

    if system() == "Darwin":
        return (
            "On macOS, Homebrew GStreamer can be installed while Azure Speech "
            "SDK still cannot load it for compressed MP3 input. Microsoft "
            "documents this GStreamer path for Linux and Windows, not macOS.\n\n"
            "Run tests/unit/tts/test_tts_providers.py in Linux/CI for now, or "
            "change this helper to decode MP3 to WAV/PCM before Azure STT.\n\n"
            f"{linux_install}"
        )

    return (
        "Install GStreamer before running tests/unit/tts/test_tts_providers.py.\n\n"
        f"{linux_install}"
    )


class AzureSTTHelper:
    """Thin wrapper around Azure Speech SDK for speech-to-text in tests."""

    @staticmethod
    def require_mp3_support() -> None:
        """Fail clearly when Azure Speech SDK cannot read MP3 test audio."""
        support_error = _azure_speech_mp3_support_error()
        if support_error is None:
            return

        pytest.fail(
            "Azure Speech SDK cannot read MP3 audio because GStreamer is not "
            "installed or is not visible at runtime.\n\n"
            f"{_gstreamer_failure_help()}\n\n"
            f"Original Azure SDK error: {support_error}",
            pytrace=False,
        )

    @staticmethod
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
        retry=retry_if_exception_type(RuntimeError),
    )
    def transcribe(
        audio_bytes: bytes,
        language_code: str,
        azure_access: AzureProviderAccess,
    ) -> str:
        """Transcribe MP3 audio bytes via Azure continuous recognition.

        Uses continuous recognition instead of ``recognize_once`` so that
        pauses inside the audio (e.g. between slash-separated alternatives)
        do not cause premature truncation.
        """
        speech_config = speechsdk.SpeechConfig(
            subscription=azure_access.subscription_key.get_secret_value(),
            region=azure_access.region,
        )
        speech_config.speech_recognition_language = language_code

        compressed_format = speechsdk.audio.AudioStreamFormat(
            compressed_stream_format=speechsdk.audio.AudioStreamContainerFormat.MP3
        )
        stream = speechsdk.audio.PushAudioInputStream(compressed_format)
        stream.write(audio_bytes)
        stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        # -- continuous recognition: collect all segments ----------------
        done = threading.Event()
        segments: list[str] = []
        errors: list[str] = []

        def _on_recognized(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                segments.append(evt.result.text)

        def _on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
            cancellation = evt.result.cancellation_details
            if cancellation.reason == speechsdk.CancellationReason.Error:
                errors.append(
                    f"Azure STT failed: {cancellation.reason} — {cancellation.error_details}"
                )
            done.set()

        def _on_session_stopped(evt: speechsdk.SessionEventArgs) -> None:
            done.set()

        recognizer.recognized.connect(_on_recognized)
        recognizer.canceled.connect(_on_canceled)
        recognizer.session_stopped.connect(_on_session_stopped)

        recognizer.start_continuous_recognition()
        done.wait(timeout=_CONTINUOUS_TIMEOUT_S)
        recognizer.stop_continuous_recognition()

        if errors:
            raise RuntimeError(errors[0])

        return " ".join(segments)
