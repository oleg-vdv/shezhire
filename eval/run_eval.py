"""Run the model on synthetic stories and score it before and after verification.

    python eval/run_eval.py --model gemma4:12b
    python eval/run_eval.py --model gemma4:12b --only-score   # reuse cached outputs

Raw model outputs are cached in eval/runs/<model>/ so the scoring can be rerun
without calling the model again. Results go to eval/results-<model>.json.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shezhire.extract import extract  # noqa: E402
from shezhire.lexicon import EDGE  # noqa: E402
from shezhire.tree import person_key  # noqa: E402
from shezhire.verify import edge_of, verify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def truth_edges(t):
    E = set()
    for p, c in t["parent"]:
        E.add(("parent", person_key(p), person_key(c)))
    for a, b in t["spouse"]:
        E.add(("spouse",) + tuple(sorted((person_key(a), person_key(b)))))
    for a, b in t["sibling"]:
        E.add(("sibling",) + tuple(sorted((person_key(a), person_key(b)))))
    par = {}
    for p, c in t["parent"]:
        par.setdefault(person_key(c), set()).add(person_key(p))
    for c, ps in par.items():
        for p in ps:
            for g in par.get(p, ()):
                E.add(("grandparent", g, c))
    return E


def claim_edge(r):
    if r["rel"] not in EDGE or not r["a"] or not r["b"]:
        return None
    kind, x, y = edge_of(r)
    x, y = person_key(x), person_key(y)
    if kind in ("spouse", "sibling"):
        x, y = sorted((x, y))
    return (kind, x, y)


def score_story(doc, verified):
    T = truth_edges(doc["truth"])
    raw, kept = set(), set()
    per_claim = []
    for r in verified["relations"]:
        e = claim_edge(r)
        ok = e in T if e else False
        per_claim.append({"edge": e, "true": ok, "status": r["status"], "reason": r["reason"]})
        if e:
            raw.add(e)
            if r["status"] == "verified":
                kept.add(e)
    return T, raw, kept, per_claim


def prf(pred, truth):
    tp = len(pred & truth)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(truth) if truth else 0.0
    return tp, p, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:12b")
    ap.add_argument("--data", default=str(ROOT / "data" / "synthetic"))
    ap.add_argument("--only-score", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cache = ROOT / "eval" / "runs" / a.model.replace(":", "_")
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(a.data).glob("*.json"))
    if a.limit:
        files = files[: a.limit]

    tot = Counter()
    reasons_on_false = Counter()
    reasons_on_true = Counter()
    seconds = []
    stories = []
    for fp in files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        cp = cache / fp.name
        if cp.exists():
            ext = json.loads(cp.read_text(encoding="utf-8"))
        elif a.only_score:
            continue
        else:
            ext = extract(doc, model=a.model)
            cp.write_text(json.dumps(ext, ensure_ascii=False, indent=1), encoding="utf-8")
        seconds.append(ext.get("_meta", {}).get("seconds") or 0)
        ver = verify(ext, doc)
        T, raw, kept, claims = score_story(doc, ver)
        decoys = {person_key(d) for d in doc.get("decoys", [])}
        for c in claims:
            if c["edge"] is None:
                tot["unusable_claims"] += 1
                continue
            if c["true"]:
                tot["true_claims"] += 1
                if c["status"] != "verified":
                    tot["true_rejected"] += 1
                    reasons_on_true[c["reason"]] += 1
            else:
                tot["false_claims"] += 1
                if c["status"] != "verified":
                    tot["false_caught"] += 1
                    reasons_on_false[c["reason"]] += 1
                if decoys & set(c["edge"][1:]):
                    tot["decoy_claims"] += 1
                    if c["status"] != "verified":
                        tot["decoy_caught"] += 1
        tp_r, p_r, r_r = prf(raw, T)
        tp_k, p_k, r_k = prf(kept, T)
        tot["truth"] += len(T)
        tot["raw"] += len(raw)
        tot["raw_tp"] += tp_r
        tot["kept"] += len(kept)
        tot["kept_tp"] += tp_k
        stories.append({"id": doc["id"], "truth": len(T), "raw": len(raw), "raw_tp": tp_r,
                        "kept": len(kept), "kept_tp": tp_k, "seconds": seconds[-1]})
        print(f"{doc['id']}: raw {tp_r}/{len(raw)}  kept {tp_k}/{len(kept)}  truth {len(T)}  {seconds[-1]}s", flush=True)

    def pct(x, y):
        return round(100 * x / y, 1) if y else None

    res = {
        "model": a.model,
        "stories": len(stories),
        "edges_in_truth": tot["truth"],
        "raw": {"edges": tot["raw"], "correct": tot["raw_tp"], "precision": pct(tot["raw_tp"], tot["raw"]),
                "recall": pct(tot["raw_tp"], tot["truth"])},
        "verified": {"edges": tot["kept"], "correct": tot["kept_tp"], "precision": pct(tot["kept_tp"], tot["kept"]),
                     "recall": pct(tot["kept_tp"], tot["truth"])},
        "claims": dict(tot),
        "false_claims_caught_pct": pct(tot["false_caught"], tot["false_claims"]),
        "true_claims_rejected_pct": pct(tot["true_rejected"], tot["true_claims"]),
        "reasons_false_caught": dict(reasons_on_false.most_common()),
        "reasons_true_rejected": dict(reasons_on_true.most_common()),
        "median_seconds": sorted(seconds)[len(seconds) // 2] if seconds else None,
        "per_story": stories,
    }
    out = ROOT / "eval" / f"results-{a.model.replace(':', '_')}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "per_story"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
