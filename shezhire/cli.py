"""Command line.

    python -m shezhire.cli transcribe story.m4a --narrator Нұрлан -o story.json
    python -m shezhire.cli run story.json -o tree.html
    python -m shezhire.cli run story.json --extraction cached.json -o tree.html
"""

import argparse
import json
from pathlib import Path

from .render import render
from .tree import build
from .verify import verify


def cmd_run(a):
    transcript = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    if a.narrator:
        transcript["narrator"] = a.narrator
    if a.extraction:
        ext = json.loads(Path(a.extraction).read_text(encoding="utf-8"))
    else:
        from .extract import extract
        ext = extract(transcript, model=a.model) if a.model else extract(transcript)
        if a.save_extraction:
            Path(a.save_extraction).write_text(json.dumps(ext, ensure_ascii=False, indent=1), encoding="utf-8")
    ver = verify(ext, transcript)
    tree = build(ver, narrator=transcript.get("narrator", ""))
    out = render(tree, transcript, a.out, audio_url=a.audio)
    rel = ver["relations"]
    ok = sum(1 for r in rel if r["status"] == "verified")
    print(f"{ok}/{len(rel)} relations verified, {len(rel) - ok} ghosts, "
          f"{tree['generations_up']} generations up, {len(tree['conflicts'])} conflicts -> {out}")


def cmd_transcribe(a):
    from .transcribe import transcribe
    t = transcribe(a.audio, language=a.language, model_size=a.whisper)
    t["narrator"] = a.narrator
    t["audio"] = Path(a.audio).name
    Path(a.out).write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(t['segments'])} segments -> {a.out}")


def main():
    ap = argparse.ArgumentParser(prog="shezhire")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="transcript -> verified family tree page")
    r.add_argument("transcript")
    r.add_argument("-o", "--out", default="tree.html")
    r.add_argument("--model")
    r.add_argument("--narrator")
    r.add_argument("--extraction", help="reuse a saved model output instead of calling the model")
    r.add_argument("--save-extraction")
    r.add_argument("--audio", help="audio file or URL to play quotes from")
    r.set_defaults(fn=cmd_run)
    t = sub.add_parser("transcribe", help="audio -> transcript with timestamps (faster-whisper)")
    t.add_argument("audio")
    t.add_argument("--narrator", required=True)
    t.add_argument("--language", default=None)
    t.add_argument("--whisper", default="large-v3")
    t.add_argument("-o", "--out", default="transcript.json")
    t.set_defaults(fn=cmd_transcribe)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
