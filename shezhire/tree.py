"""Assemble verified relations into a family tree and check it for contradictions."""

from collections import defaultdict

from .lexicon import EDGE
from .text import name_stem, norm
from .verify import edge_of

MALE = {"father", "son", "husband", "brother", "grandfather"}
FEMALE = {"mother", "daughter", "wife", "sister", "grandmother"}


def person_key(name: str) -> str:
    parts = norm(name).split()
    if not parts:
        return ""
    return " ".join([name_stem(parts[0])] + parts[1:2])


def build(verified: dict, narrator: str = "") -> dict:
    people: dict[str, dict] = {}
    edges: list[dict] = []

    def add(name):
        k = person_key(name)
        p = people.setdefault(k, {"id": k, "name": name.strip(), "sex": set(), "facts": [], "ghost_only": True})
        # keep the shortest spelling, it is usually the nominative
        if len(name.strip()) < len(p["name"]):
            p["name"] = name.strip()
        return k

    for r in verified["relations"]:
        if r["rel"] not in EDGE or not r["a"] or not r["b"]:
            continue
        kind, x, y = edge_of(r)
        kx, ky = add(x), add(y)
        ghost = r["status"] != "verified"
        if not ghost:
            people[kx]["ghost_only"] = False
            people[ky]["ghost_only"] = False
            if r["rel"] in MALE:
                people[add(r["a"])]["sex"].add("m")
            if r["rel"] in FEMALE:
                people[add(r["a"])]["sex"].add("f")
        edges.append({"kind": kind, "from": kx, "to": ky, "ghost": ghost,
                      "reason": r.get("reason"), "claim": r})

    for f in verified["facts"]:
        if not f["person"]:
            continue
        k = add(f["person"])
        people[k]["facts"].append(f)
        if f["status"] == "verified":
            people[k]["ghost_only"] = False

    edges = _dedupe(edges)
    conflicts = _conflicts(people, edges)
    levels = _levels(people, edges)
    nk = person_key(narrator) if narrator else None
    for p in people.values():
        p["sex"] = "".join(sorted(p["sex"]))
        p["level"] = levels.get(p["id"], 0)
        p["narrator"] = p["id"] == nk
    return {"people": list(people.values()), "edges": edges, "conflicts": conflicts,
            "generations_up": _generations_up(nk, edges) if nk in people else 0}


def _dedupe(edges):
    """Same edge from two quotes: keep one, verified wins over ghost."""
    seen = {}
    for e in edges:
        a, b = e["from"], e["to"]
        if e["kind"] in ("spouse", "sibling"):
            a, b = sorted((a, b))
        key = (e["kind"], a, b)
        if key not in seen or (seen[key]["ghost"] and not e["ghost"]):
            seen[key] = e
    return list(seen.values())


def _conflicts(people, edges):
    out = []
    parents = defaultdict(set)
    for e in edges:
        if e["kind"] == "parent" and not e["ghost"]:
            parents[e["to"]].add(e["from"])
    for child, ps in parents.items():
        if len(ps) > 2:
            out.append({"type": "too_many_parents", "person": child, "with": sorted(ps)})
        sexes = [people[p]["sex"] for p in ps]
        if sum(1 for s in sexes if s == {"m"}) > 1:
            out.append({"type": "two_fathers", "person": child, "with": sorted(ps)})
        if sum(1 for s in sexes if s == {"f"}) > 1:
            out.append({"type": "two_mothers", "person": child, "with": sorted(ps)})
    for p in people.values():
        if p["sex"] == {"m", "f"}:
            out.append({"type": "both_male_and_female", "person": p["id"]})
    # a person cannot be their own ancestor
    graph = defaultdict(list)
    for e in edges:
        if e["kind"] in ("parent", "grandparent") and not e["ghost"]:
            graph[e["from"]].append(e["to"])
    state = {}

    def dfs(u, stack):
        state[u] = 1
        for v in graph[u]:
            if state.get(v) == 1:
                out.append({"type": "cycle", "person": v, "with": stack + [v]})
            elif v not in state:
                dfs(v, stack + [v])
        state[u] = 2

    for u in list(graph):
        if u not in state:
            dfs(u, [u])
    return out


def _levels(people, edges):
    """Generation level: ancestors at 0, each child one below its parent."""
    lvl = {k: 0 for k in people}
    for _ in range(len(people) + 2):
        changed = False
        for e in edges:
            step = {"parent": 1, "grandparent": 2}.get(e["kind"])
            if step and lvl[e["to"]] < lvl[e["from"]] + step:
                lvl[e["to"]] = lvl[e["from"]] + step
                changed = True
            if e["kind"] in ("spouse", "sibling"):
                m = max(lvl[e["from"]], lvl[e["to"]])
                if lvl[e["from"]] != m or lvl[e["to"]] != m:
                    lvl[e["from"]] = lvl[e["to"]] = m
                    changed = True
        if not changed:
            break
    return lvl


def _generations_up(start, edges):
    """How many generations of verified ancestors stand above the narrator."""
    up = defaultdict(list)
    for e in edges:
        if not e["ghost"] and e["kind"] in ("parent", "grandparent"):
            up[e["to"]].append((e["from"], 1 if e["kind"] == "parent" else 2))
    best = 0
    stack = [(start, 0, {start})]
    while stack:
        u, d, seen = stack.pop()
        best = max(best, d)
        for v, w in up[u]:
            if v not in seen:
                stack.append((v, d + w, seen | {v}))
    return best
