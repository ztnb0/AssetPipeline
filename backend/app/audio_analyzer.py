from pathlib import Path

from faster_whisper import WhisperModel

from .analyzer import analyze_text
from .config import settings


_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(settings.asr_model_size, device="cpu", compute_type="int8")
    return _model


def analyze_audio(path: Path) -> dict:
    segments, info = _get_model().transcribe(
        str(path), beam_size=3, vad_filter=True, condition_on_previous_text=False
    )
    transcript = "".join(segment.text for segment in segments).strip()
    if not transcript:
        raise ValueError("ASR 未识别出可用文本")
    result = analyze_text(transcript)
    result["transcript"] = transcript
    result["language"] = info.language
    result["language_probability"] = round(info.language_probability, 4)
    return result
