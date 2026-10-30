"""Speech to timestamped segments with faster-whisper, fully offline.

The segment timestamps are what lets every line of the tree play back the
exact seconds where it was said.
"""


def transcribe(path: str, language: str | None = None, model_size: str = "large-v3") -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, info = model.transcribe(path, language=language, vad_filter=True)
    out = []
    for i, s in enumerate(segments):
        out.append({"id": i, "start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()})
    return {"language": info.language, "segments": out}
