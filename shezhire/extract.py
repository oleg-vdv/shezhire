"""Ask a local open-weight model to read a family story and list relations.

The model is only a reader here. Everything it returns goes through
verify.py, and nothing reaches the tree without a quote that the code found
in the transcript.
"""

import json
import os
import time

import httpx

OLLAMA = os.environ.get("SHEZHIRE_OLLAMA", "http://localhost:11434")
MODEL = os.environ.get("SHEZHIRE_MODEL", "gemma4:12b")

RELATIONS = ["father", "mother", "son", "daughter", "husband", "wife",
             "brother", "sister", "grandfather", "grandmother"]

SYSTEM = f"""You read transcripts of elders telling family stories in Russian or Kazakh
and extract the family tree.

Return JSON: {{"relations": [...], "facts": [...]}}.

Each relation: {{"a": "<name>", "rel": "<one of {', '.join(RELATIONS)}>", "b": "<name>",
"seg": <segment id>, "quote": "<exact words copied from that segment>"}}
It means: a is the <rel> of b. Example: "Асқар is the father of Мария" ->
{{"a": "Асқар", "rel": "father", "b": "Мария", ...}}.

Each fact: {{"person": "<name>", "kind": "born" | "died" | "place" | "occupation",
"value": "<value>", "seg": <segment id>, "quote": "<exact words>"}}

Rules:
- The narrator is {{narrator}}. When the speaker says "я", "мой", "мен", "менің", use the narrator's name.
- Use names exactly as spoken, in the nominative form.
- quote must be copied word for word from the segment, not paraphrased.
- Only people who have a name. Skip unnamed people ("какой-то сосед").
- Do not add relations you only guess from context."""


def _segments_block(transcript: dict) -> str:
    lines = []
    for s in transcript["segments"]:
        lines.append(f"[{s['id']}] {s['text']}")
    return "\n".join(lines)


def extract(transcript: dict, model: str = MODEL, timeout: float = 600) -> dict:
    narrator = transcript.get("narrator", "the speaker")
    system = SYSTEM.replace("{narrator}", narrator)
    user = "Transcript segments:\n" + _segments_block(transcript)
    t0 = time.time()
    r = httpx.post(
        f"{OLLAMA}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    raw = body["message"]["content"]
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        out = {"relations": [], "facts": [], "parse_error": raw[:500]}
    out.setdefault("relations", [])
    out.setdefault("facts", [])
    out["_meta"] = {"model": model, "seconds": round(time.time() - t0, 1),
                    "eval_count": body.get("eval_count")}
    return out
