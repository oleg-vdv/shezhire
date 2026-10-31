"""Check every claim the model made against the transcript.

A claim survives only if code can point at the words that support it:
the quote exists in the transcript, both names appear in it, and it contains
a kinship word of the right kind. Everything else becomes a ghost: shown in
the tree as a dashed line with the reason, never as a fact.
"""

import re

from .lexicon import EDGE, FIRST_PERSON, GROUP_OF, STEMS
from .text import has_stem, mentions_name, name_stem, norm, quote_score

QUOTE_MIN = 85.0
ROLE_WORDS = ["дед", "бабушк", "отец", "мать", "мама", "папа", "ата", "әже", "әке", "ана"]
ROLE_NAMES = {"дед", "дедушка", "бабушка", "отец", "мать", "мама", "папа", "ата", "атам", "әже", "әжем",
              "әке", "әкем", "ана", "анам", "прадед", "прабабушка"}  # partial-ratio threshold for "this quote is in the segment"

REASONS = {
    "bad_relation": "relation type the tree does not know",
    "self_relation": "a person related to themselves",
    "invented_person": "this name is never spoken in the recording",
    "quote_not_found": "the quoted words are not in the recording",
    "name_not_in_quote": "the quote does not mention both people",
    "no_kinship_word": "the quote has no kinship word for this relation",
    "value_not_in_quote": "the value is not in the quote",
    "kin_word_is_narrators": "the kinship word is about the narrator, not these two",
    "both_listed_as_children": "both are listed as children in the same breath",
    "role_not_name": "a role word used as if it were a name",
}


def _seg_by_id(transcript):
    return {s["id"]: s for s in transcript["segments"]}


def _seg_id(v):
    """Small models write the segment as 3, "3", [3, 4] or "seg 3"."""
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, str):
        m = re.search(r"\d+", v)
        v = int(m.group()) if m else None
    return v if isinstance(v, int) else None


def _find_quote(quote, transcript, seg_id):
    """Return (segment, score). Prefer the segment the model named."""
    seg_id = _seg_id(seg_id)
    segs = _seg_by_id(transcript)
    best, best_score = None, 0.0
    if seg_id in segs:
        sc = quote_score(quote, segs[seg_id]["text"])
        if sc >= QUOTE_MIN:
            return segs[seg_id], sc
        best, best_score = segs[seg_id], sc
    for s in transcript["segments"]:
        sc = quote_score(quote, s["text"])
        if sc > best_score:
            best, best_score = s, sc
    # quotes sometimes span two neighbouring segments
    ss = transcript["segments"]
    for i in range(len(ss) - 1):
        joined = {"id": ss[i]["id"], "start": ss[i].get("start"), "end": ss[i + 1].get("end"),
                  "text": ss[i]["text"] + " " + ss[i + 1]["text"]}
        sc = quote_score(quote, joined["text"])
        if sc > best_score + 5:
            best, best_score = joined, sc
    return best, best_score


def _is_narrator(name, narrator):
    return bool(narrator) and norm(name).split()[:1] == norm(narrator).split()[:1]


def _person_in(text, name, narrator, aliases=None):
    if mentions_name(text, name):
        return True
    stems = (aliases or {}).get(norm(name))
    if stems and has_stem(text, stems):
        return True
    if _is_narrator(name, narrator):
        toks = set(norm(text).split())
        return any(w in toks for w in FIRST_PERSON)
    return False


def _whole_text(transcript):
    return " ".join(s["text"] for s in transcript["segments"])


def verify_relation(rel, transcript, aliases=None):
    narrator = transcript.get("narrator", "")
    a, b, r = str(rel.get("a", "")).strip(), str(rel.get("b", "")).strip(), str(rel.get("rel", "")).strip().lower()
    quote = str(rel.get("quote", ""))
    out = {"a": a, "rel": r, "b": b, "quote": quote, "seg": rel.get("seg"),
           "status": "ghost", "reason": None, "evidence": None}

    if r not in GROUP_OF:
        out["reason"] = "bad_relation"
        return out
    if norm(a) == norm(b):
        out["reason"] = "self_relation"
        return out
    for name in (a, b):
        if has_stem(name, ROLE_WORDS) and len(norm(name).split()) == 1 and norm(name) in ROLE_NAMES:
            out["reason"] = "role_not_name"
            return out

    whole = _whole_text(transcript)
    for name in (a, b):
        if not _person_in(whole, name, narrator):
            out["reason"] = "invented_person"
            out["missing"] = name
            return out

    seg, score = _find_quote(quote, transcript, rel.get("seg"))
    out["quote_score"] = round(score, 1)
    if seg is None or score < QUOTE_MIN:
        out["reason"] = "quote_not_found"
        return out

    # judge on the words actually in the segment, not on the model's copy.
    # A name may sit in the sentence just before ("Моего прадеда звали Сәкен.
    # Его жену звали Мария."), the kinship word must be in the quoted one.
    # At least one of the two must be named literally in the quoted sentence:
    # a pronoun, a role word and a previous sentence are never enough together.
    text = seg["text"]
    prev = _prev_segment(transcript, seg)
    span = seg
    literal = 0
    for name in (a, b):
        if mentions_name(text, name):
            literal += 1
            continue
        if _person_in(text, name, narrator, aliases):
            continue
        if prev and _person_in(prev["text"], name, narrator, aliases):
            span = _join(prev, seg)
            out["context"] = "name in the previous sentence"
            continue
        out["reason"] = "name_not_in_quote"
        out["evidence"] = _evidence(seg)
        return out
    if literal == 0:
        out["reason"] = "name_not_in_quote"
        out["evidence"] = _evidence(seg)
        return out

    word = has_stem(text, STEMS[GROUP_OF[r]])
    if not word:
        out["reason"] = "no_kinship_word"
        out["evidence"] = _evidence(seg)
        return out

    # "Мою маму зовут Ақмарал, она вышла замуж за Берік": "маму" is the
    # narrator's mother, so it cannot support "Ақмарал is Берік's mother".
    hits = _kin_hits(text, STEMS[GROUP_OF[r]])
    if hits and all(h["mine"] for h in hits) and not any(_is_narrator(n, narrator) for n in (a, b)):
        out["reason"] = "kin_word_is_narrators"
        out["evidence"] = _evidence(seg)
        return out

    # "двое детей: Данияр и Ерлан" lists two children; they are not
    # parent and child of each other.
    if GROUP_OF[r] == "parent" and _both_listed_as_children(text, a, b):
        out["reason"] = "both_listed_as_children"
        out["evidence"] = _evidence(seg)
        return out

    out["status"] = "verified"
    out["kin_word"] = word
    out["evidence"] = _evidence(span)
    return out


MY = {"мой", "моя", "мою", "моего", "моей", "мои", "моих", "моему", "менің", "my"}
CHILD_WORDS = ["дет", "ребен", "ребён", "сын", "сыновь", "доч", "бала", "ұл", "қыз", "children", "son", "daughter"]


def _kin_hits(text, stems):
    """Every kinship word in text, and whether it is the narrator's own
    ("мой отец", "мою маму", Kazakh "әкем", "анам", "атам", "әжем")."""
    toks = norm(text).split()
    out = []
    for i, t in enumerate(toks):
        for s in stems:
            s = norm(s)
            if " " in s or not t.startswith(s):
                continue
            mine = (i > 0 and toks[i - 1] in MY) or (len(t) == len(s) + 1 and t.endswith("м"))                 or (len(t) == len(s) + 2 and t[-2:] in ("ым", "ім"))
            out.append({"word": t, "mine": mine})
            break
    return out


def _both_listed_as_children(text, a, b):
    toks = norm(text).split()
    first = next((i for i, t in enumerate(toks) if any(t.startswith(w) for w in CHILD_WORDS)), None)
    if first is None:
        return False

    def pos(name):
        st = name_stem(name)
        return next((i for i, t in enumerate(toks) if st and t.startswith(st)), None)

    pa, pb = pos(a), pos(b)
    return pa is not None and pb is not None and pa > first and pb > first


def _prev_segment(transcript, seg):
    ss = transcript["segments"]
    for i, s in enumerate(ss):
        if s["id"] == seg["id"]:
            return ss[i - 1] if i > 0 else None
    return None


def _join(a, b):
    return {"id": a["id"], "start": a.get("start"), "end": b.get("end"), "text": a["text"] + " " + b["text"]}


def verify_fact(fact, transcript, aliases=None):
    narrator = transcript.get("narrator", "")
    person = str(fact.get("person", "")).strip()
    value = str(fact.get("value", "")).strip()
    quote = str(fact.get("quote", ""))
    out = {"person": person, "kind": fact.get("kind"), "value": value, "quote": quote,
           "seg": fact.get("seg"), "status": "ghost", "reason": None, "evidence": None}

    if not _person_in(_whole_text(transcript), person, narrator):
        out["reason"] = "invented_person"
        return out
    seg, score = _find_quote(quote, transcript, fact.get("seg"))
    if seg is None or score < QUOTE_MIN:
        out["reason"] = "quote_not_found"
        return out
    text = seg["text"]
    if not _person_in(text, person, narrator, aliases):
        out["reason"] = "name_not_in_quote"
        out["evidence"] = _evidence(seg)
        return out
    digits = re.findall(r"\d{3,4}", value)
    if digits:
        ok = all(d in text for d in digits)
    else:
        ok = bool(value) and has_stem(text, [w[:max(3, len(w) - 2)] for w in norm(value).split() if len(w) > 2]) is not None
    if not ok:
        out["reason"] = "value_not_in_quote"
        out["evidence"] = _evidence(seg)
        return out
    out["status"] = "verified"
    out["evidence"] = _evidence(seg)
    return out


def _evidence(seg):
    return {"seg": seg["id"], "start": seg.get("start"), "end": seg.get("end"), "text": seg["text"]}


# once code has verified "X is my father", the word "отец" in a later sentence
# can stand for X. Only roles relative to the narrator, only after verification.
ROLE_STEMS = {
    "father": ["отец", "отц", "пап", "әке", "көке"],
    "mother": ["мам", "мать", "матер", "ана", "шеше"],
    "grandfather": ["дед", "ата"],
    "grandmother": ["бабушк", "әже"],
    "brother": ["брат", "аға", "іні"],
    "sister": ["сестр", "әпке", "қарындас", "сіңлі"],
}


def _aliases(rels, narrator):
    out = {}
    if not narrator:
        return out
    for r in rels:
        if r["status"] != "verified" or r["rel"] not in ROLE_STEMS:
            continue
        if _is_narrator(r["b"], narrator) and not _is_narrator(r["a"], narrator):
            out.setdefault(norm(r["a"]), [])
            out[norm(r["a"])] += ROLE_STEMS[r["rel"]]
    return out


def verify(extraction, transcript):
    narrator = transcript.get("narrator", "")
    raw_rels = [r for r in extraction.get("relations", []) if isinstance(r, dict)]
    raw_facts = [f for f in extraction.get("facts", []) if isinstance(f, dict)]
    aliases = {}
    for _ in range(3):
        rels = [verify_relation(r, transcript, aliases) for r in raw_rels]
        new = _aliases(rels, narrator)
        if new == aliases:
            break
        aliases = new
    for r in rels:
        if r["status"] == "verified" and any(norm(n) in aliases and not mentions_name((r["evidence"] or {}).get("text", ""), n)
                                             for n in (r["a"], r["b"])):
            r["context"] = "person named by role (" + ", ".join(sorted({n for n in (r["a"], r["b"]) if norm(n) in aliases})) + ")"
    facts = [verify_fact(f, transcript, aliases) for f in raw_facts]
    return {"relations": rels, "facts": facts, "aliases": aliases}


def edge_of(rel):
    """Turn a verified or ghost relation into (kind, parent_or_x, child_or_y)."""
    kind, direction = EDGE[rel["rel"]]
    if direction == "b_parent":
        return kind, rel["b"], rel["a"]
    return kind, rel["a"], rel["b"]
