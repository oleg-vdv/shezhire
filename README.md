# Shezhire

**A family tree from recorded stories, built by a local open-weight model and checked line by line against the recording.**

*Шежіре* is the Kazakh word for a genealogy. Kazakh families keep track of seven generations of ancestors (*жеті ата*), mostly through stories told by the oldest relatives. When those relatives are gone, the stories go with them.

Shezhire takes a recording of a grandmother telling the family story, lets an open-weight model (Gemma 4 through Ollama) read the transcript, and builds the tree. The model is not trusted. Every link it proposes goes through code that has to find, in the recording itself:

1. the quoted words, in the segment the model points to (or the one right next to it),
2. both people, named in that sentence: by name, by a role already proven ("my grandfather" once we know who he is), or by "I/my" for the narrator. At least one of them must be named literally,
3. a kinship word of the right kind, in Russian, Kazakh or English (*отец, әкем, жена, бауыр, ата, әже...*).

What passes is drawn in ink, with a link to the second of audio where it was said. What fails is a **ghost**: it stays on the page, dashed, with the reason it was turned away. Invented relatives, the neighbour the model promoted to an uncle, a birth year nobody said.

## Run it

```bash
pip install -e .            # httpx, rapidfuzz
pip install -e ".[audio]"   # + faster-whisper, for recordings

ollama pull gemma4:12b

# audio -> timestamped transcript (offline)
python -m shezhire.cli transcribe grandma.m4a --narrator Әлия -o story.json

# transcript -> verified tree page
python -m shezhire.cli run story.json --audio grandma.m4a -o tree.html
```

Environment: `SHEZHIRE_OLLAMA` (default `http://localhost:11434`), `SHEZHIRE_MODEL` (default `gemma4:12b`).

A transcript is plain JSON:

```json
{"narrator": "Әлия",
 "segments": [{"id": 0, "start": 0.0, "end": 6.1, "text": "Я Әлия, это мне әжем рассказывала..."}]}
```

## How well it works

`eval/` has 30 synthetic family stories with a known true tree and the traps real recordings have: a named neighbour who is "like family", a child whose name nobody remembers, "he married in 1942" with the husband in the previous sentence, Kazakh kinship words inside Russian speech.

```bash
python eval/make_synthetic.py --n 30 --seed 7
python eval/run_eval.py --model gemma4:12b
```

Results are in `eval/results-*.json`; raw model outputs are cached in `eval/runs/` so the scoring can be rerun without a model.

## What the check does not catch

- **Direction.** "Асқар is the son of Мұрат" and "Мұрат is the son of Асқар" both contain the same names and the word *сын*. The verifier accepts either; the tree's contradiction check (two fathers, a person who is their own ancestor) catches some of these, not all.
- **Long pronoun chains.** If the person was named three sentences ago, the link is rejected even when it is true. This is a deliberate trade: a missed true link is a gap a family can fill, an invented one is a lie on the page.
- **Synthetic stories are easier than real ones.** Real recordings have crosstalk, dialect and Whisper errors on Kazakh names.

## Files

| Path | What |
|---|---|
| `shezhire/extract.py` | prompt and call to the local model |
| `shezhire/verify.py` | the check: quote, names, kinship word, role aliases |
| `shezhire/tree.py` | tree assembly, generations, contradictions |
| `shezhire/page.html`, `render.py` | one self-contained page per family |
| `shezhire/transcribe.py` | faster-whisper, offline |
| `eval/` | synthetic stories, scoring |
| `kaggle/build.py` | runs the eval on a free Kaggle GPU when there is no GPU at home |

MIT license.
