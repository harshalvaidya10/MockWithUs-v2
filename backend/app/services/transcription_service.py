from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

_MODEL_LOCK = Lock()
_TRANSCRIPTION_MODEL: Any | None = None


class TranscriptionError(Exception):
    """Base class for transcription failures."""


class TranscriptionInputError(TranscriptionError):
    """Raised when uploaded audio cannot be transcribed into speech text."""


def _load_model() -> Any:
    """Lazily construct and cache the faster-whisper model instance."""
    global _TRANSCRIPTION_MODEL

    if _TRANSCRIPTION_MODEL is not None:
        return _TRANSCRIPTION_MODEL

    with _MODEL_LOCK:
        if _TRANSCRIPTION_MODEL is not None:
            return _TRANSCRIPTION_MODEL

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            missing_dependency = getattr(exc, "name", None) or str(exc)
            raise TranscriptionError(
                "Audio transcription dependencies are unavailable "
                f"({missing_dependency}). Install backend requirements and rebuild the backend service."
            ) from exc

        logger.info(
            "Loading transcription model '%s' on device '%s' (%s).",
            settings.transcription_model_size,
            settings.transcription_device,
            settings.transcription_compute_type,
        )
        try:
            _TRANSCRIPTION_MODEL = WhisperModel(
                settings.transcription_model_size,
                device=settings.transcription_device,
                compute_type=settings.transcription_compute_type,
            )
        except Exception as exc:
            raise TranscriptionError(
                "Audio transcription model failed to initialize. "
                "Check transcription model settings and backend runtime dependencies."
            ) from exc

    return _TRANSCRIPTION_MODEL


def transcribe_audio_file(audio_path: str) -> str:
    """Transcribe a saved audio file into plain text."""
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionInputError("Uploaded audio file is missing.")
    if path.stat().st_size == 0:
        raise TranscriptionInputError("Uploaded audio file is empty.")

    model = _load_model()

    try:
        segments, _ = model.transcribe(
            str(path),
            beam_size=1,
            vad_filter=True,
        )
    except Exception as exc:
        raise TranscriptionInputError(
            "Could not transcribe audio. Please record a clear spoken answer and try again."
        ) from exc

    transcript = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
    if not transcript:
        raise TranscriptionInputError(
            "No speech was detected in the recording. Please try again."
        )

    return transcript
