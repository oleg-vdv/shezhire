"""Render a verified tree as one self-contained HTML page.

Verified links are drawn in ink. Ghosts, the links the model claimed but the
code could not find in the recording, stay on the page in pencil with the
reason, so the family can see what was dropped and why.
"""

import json
from pathlib import Path

from .verify import REASONS

TEMPLATE = (Path(__file__).parent / "page.html").read_text(encoding="utf-8")


def render(tree: dict, transcript: dict, out_path: str | Path, audio_url: str | None = None) -> Path:
    data = {
        "narrator": transcript.get("narrator", ""),
        "title": transcript.get("title") or transcript.get("id", ""),
        "audio": audio_url or transcript.get("audio"),
        "segments": transcript["segments"],
        "tree": tree,
        "reasons": REASONS,
    }
    blob = json.dumps(data, ensure_ascii=False, default=list).replace("</", "<\\/")
    html = TEMPLATE.replace("/*DATA*/null", blob)
    out = Path(out_path)
    out.write_text(html, encoding="utf-8")
    return out
