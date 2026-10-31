# Results

All numbers are recomputed from the cached model outputs in `eval/runs/` with the current `shezhire/verify.py`:

```bash
python eval/run_eval.py --model <model> [--data data/holdout] --only-score
```

"Tree links" counts every link in the true family tree, including ones the story never says out loud (a grandmother's link to a grandchild, for example), so recall against it is low by design.

## Gemma 4 12B

| Prompt | Set | Proposed | Correct before | Ghosts caught | Kept | Correct after | True links lost | Recall of tree links |
|---|---|---|---|---|---|---|---|---|
| default | tuned on | 407 | 85.5% | 59 / 59 | 303 | 100% | 46 / 350 | 43.0% |
| default | held out | 407 | 85.5% | 59 / 59 | 290 | 100% | 59 / 351 | 44.6% |
| short (first) | tuned on | 334 | 94.6% | 18 / 18 | 246 | 100% | 82 / 331 | 34.9% |
| short (first) | held out | 338 | 95.3% | 16 / 16 | 239 | 100% | 99 / 343 | 36.8% |

The default prompt asks for the narrator's own links and warns about great-grandparents. The model proposes more and makes more mistakes, the check catches all of them, and more true links survive.

## Gemma 4 E2B (it-qat)

| Prompt | Set | Proposed | Correct before | Ghosts caught | Kept | Correct after | True links lost |
|---|---|---|---|---|---|---|---|
| default | tuned on | 378 | 72.2% | 105 / 105 | 44 | 100% | 242 / 286 |
| default | held out | 372 | 72.8% | 102 / 103 | 43 | 97.7% | 244 / 286 |
| short (first) | tuned on | 291 | 74.9% | 70 / 73 | 161 | 98.1% | 60 / 220 |
| short (first) | held out | 303 | 71.3% | 77 / 87 | 150 | 93.3% | 79 / 220 |

With the longer default prompt the small model mostly stops copying quotes (`quote_not_found` on 232 of its true claims), so the check rejects nearly everything. The tree comes out almost empty rather than wrong.

## Thinking mode

The first run left Gemma 4's thinking on. The 12B model took about four minutes per story and returned no usable JSON for almost all of them. `"think": false` is now the default (`SHEZHIRE_THINK=1` turns it back on).
