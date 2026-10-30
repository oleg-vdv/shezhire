"""Text normalisation and fuzzy matching shared by the verifier and the eval."""

import re

from rapidfuzz import fuzz

VOWELS = set("аеёиоуыэюяәіөүұaeiouy")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def norm(s: str) -> str:
    s = s.lower().replace("ё", "е").replace("—", " ").replace("–", " ")
    s = _PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return norm(s).split()


def name_stem(name: str) -> str:
    """Stem a single-word name so that case endings still match.

    Russian declines names (Мария -> Марии, Нурлан -> Нурлана) and Kazakh adds
    suffixes (Асқар -> Асқардың). Dropping one final vowel covers both.
    """
    n = norm(name).split()
    if not n:
        return ""
    w = n[0]
    if len(w) > 3 and w[-1] in VOWELS:
        w = w[:-1]
    return w


def mentions_name(text: str, name: str) -> bool:
    stem = name_stem(name)
    if not stem:
        return False
    return any(t.startswith(stem) for t in tokens(text))


def has_stem(text: str, stems: list[str]) -> str | None:
    """Return the first stem found in text, or None.

    Multi-word stems ("вышла замуж") are matched as substrings, single words
    by token prefix.
    """
    t = norm(text)
    toks = t.split()
    for s in stems:
        s = norm(s)
        if " " in s:
            if s in t:
                return s
        elif any(tok.startswith(s) for tok in toks):
            return s
    return None


def quote_score(quote: str, text: str) -> float:
    """How well the quote is contained in text, 0..100."""
    q, t = norm(quote), norm(text)
    if not q or not t:
        return 0.0
    if q in t:
        return 100.0
    return fuzz.partial_ratio(q, t)
