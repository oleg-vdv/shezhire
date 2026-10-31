"""Generate family-story transcripts with a known true tree.

Each story is told by the youngest person and mixes the things that make real
recordings hard: named neighbours who are not relatives, relatives whose names
nobody remembers, pronouns that point back to an earlier sentence, Kazakh
kinship words inside Russian speech.

    python eval/make_synthetic.py --n 30 --seed 7
"""

import argparse
import json
import random
from pathlib import Path

MALE = ["Асқар", "Нұрлан", "Ерлан", "Серік", "Бауыржан", "Жандос", "Мұрат", "Қайрат", "Темір",
        "Ахмет", "Сәкен", "Болат", "Ермек", "Данияр", "Ғалым", "Төлеген", "Жақып", "Оспан",
        "Әбдірахман", "Құдайберген", "Мақсат", "Нұржан", "Арман", "Берік"]
FEMALE = ["Бибігүл", "Гүлнар", "Айгүл", "Сәуле", "Мария", "Зәуре", "Күләш", "Ақмарал",
          "Динара", "Әсел", "Жанар", "Роза", "Меруерт", "Шолпан", "Әйгерім", "Балжан",
          "Нұрила", "Ұлжан", "Қарлыға", "Перизат"]
PLACES = ["Семей", "Аягөз", "Зайсан", "Қарқаралы", "Түркістан", "Шымкент", "Ақтөбе",
          "Павлодар", "Кокпекты", "Баянауыл"]
JOBS = ["учителем", "чабаном", "трактористом", "врачом", "бухгалтером в совхозе", "почтальоном",
        "агрономом", "шофёром"]
FRIENDS_M = ["Виктор", "Сергей", "Иван", "Тимур", "Олжас"]


class Fam:
    def __init__(self, rng):
        self.rng = rng
        self.used = set()
        self.people = {}  # name -> sex
        self.parent = []  # (parent, child)
        self.spouse = []
        self.born = {}

    def new(self, sex):
        pool = MALE if sex == "m" else FEMALE
        name = self.rng.choice([n for n in pool if n not in self.used])
        self.used.add(name)
        self.people[name] = sex
        return name


def build_family(rng):
    f = Fam(rng)
    # generation 0: great-grandparents (paternal), 1: grandparents, 2: parents, 3: narrator + siblings
    ggf, ggm = f.new("m"), f.new("f")
    f.spouse.append((ggf, ggm))
    gf = f.new("m")
    gf_sib = f.new(rng.choice("mf"))
    for c in (gf, gf_sib):
        f.parent += [(ggf, c), (ggm, c)]
    gm = f.new("f")
    f.spouse.append((gf, gm))
    father = f.new("m")
    aunt = f.new("f") if rng.random() < 0.6 else None
    for c in [father] + ([aunt] if aunt else []):
        f.parent += [(gf, c), (gm, c)]
    mother = f.new("f")
    f.spouse.append((father, mother))
    narrator = f.new(rng.choice("mf"))
    sib = f.new(rng.choice("mf")) if rng.random() < 0.7 else None
    for c in [narrator] + ([sib] if sib else []):
        f.parent += [(father, c), (mother, c)]
    y = rng.randint(1890, 1905)
    f.born = {ggf: y, gf: y + rng.randint(24, 30), father: y + rng.randint(50, 58),
              narrator: y + rng.randint(78, 88)}
    return f, dict(ggf=ggf, ggm=ggm, gf=gf, gf_sib=gf_sib, gm=gm, father=father, aunt=aunt,
                   mother=mother, narrator=narrator, sib=sib)


def word(sex, m, f):
    return m if sex == "m" else f


def tell(f, r, rng):
    s = []
    P = f.people
    n = r["narrator"]
    s.append(f"Меня зовут {n}, я расскажу про нашу семью, как мне рассказывали старшие.")
    s.append(f"Моего прадеда звали {r['ggf']}, он родился в {f.born[r['ggf']]} году под {rng.choice(PLACES)}.")
    s.append(f"Его жену, мою прабабушку, звали {r['ggm']}.")
    s.append(f"У них было двое детей: {r['gf']} и {r['gf_sib']}.")
    s.append(f"{r['gf']} – это мой дед, атам, он работал {rng.choice(JOBS)}.")
    # trap: unnamed relative
    s.append(f"Говорят, был ещё один сын, но он умер маленьким, имени уже никто не помнит.")
    # pronoun crossing a sentence
    s.append(f"В {f.born[r['gf']] + rng.randint(20, 26)} году он женился.")
    s.append(f"Жену деда звали {r['gm']}, это моя әжем.")
    # trap: named non-relative
    fr = rng.choice(FRIENDS_M)
    s.append(f"Дед всю жизнь дружил с соседом, его звали {fr}, он нам был как родной, но не родственник.")
    if r["aunt"]:
        s.append(f"У деда и {r['gm']} родились сын {r['father']} и дочь {r['aunt']}.")
    else:
        s.append(f"У деда и {r['gm']} родился сын {r['father']}, мой отец.")
    if r["aunt"]:
        s.append(f"{r['father']} – мой отец, әкем, родился в {f.born[r['father']]} году.")
    else:
        s.append(f"Отец родился в {f.born[r['father']]} году.")
    s.append(f"Мою маму зовут {r['mother']}, она вышла замуж за {r['father']} после института.")
    if r["sib"]:
        sw = word(P[r["sib"]], "брат", "сестра")
        s.append(f"У меня есть {sw} {r['sib']}, мы росли в {rng.choice(PLACES)}.")
    # trap: a relative from the gf sibling side, only by pronoun
    s.append(f"А у {r['gf_sib']} своих детей было много, но я их почти не знаю.")
    if rng.random() < 0.5:
        s.append(f"{r['ggm']} дожила до девяноста лет, всё помнила, шежіреге жазып отырды.")
    segs, t = [], 0.0
    for i, text in enumerate(s):
        dur = round(2.5 + len(text) / 14, 1)
        segs.append({"id": i, "start": round(t, 1), "end": round(t + dur, 1), "text": text})
        t += dur + 0.4
    return segs


def truth(f):
    rels = {"parent": sorted(set(f.parent)), "spouse": sorted(tuple(sorted(p)) for p in f.spouse)}
    # siblings: share both parents
    kids = {}
    for p, c in f.parent:
        kids.setdefault(c, set()).add(p)
    sibs = set()
    names = list(kids)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if kids[a] == kids[b]:
                sibs.add(tuple(sorted((a, b))))
    rels["sibling"] = sorted(sibs)
    return rels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--prefix", default="syn")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(a.n):
        f, r = build_family(rng)
        doc = {"id": f"{a.prefix}-{i:02d}", "narrator": r["narrator"], "segments": tell(f, r, rng),
               "truth": truth(f), "decoys": FRIENDS_M}
        (out / f"{a.prefix}-{i:02d}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {a.n} stories to {out}")


if __name__ == "__main__":
    main()
