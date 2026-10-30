from shezhire.tree import build
from shezhire.verify import verify, verify_relation

T = {
    "narrator": "Нұрлан",
    "segments": [
        {"id": 0, "start": 0.0, "end": 5.0, "text": "Меня зовут Нұрлан, я расскажу про нашу семью."},
        {"id": 1, "start": 5.4, "end": 9.0, "text": "Моего прадеда звали Сәкен, он родился в 1897 году под Семей."},
        {"id": 2, "start": 9.4, "end": 12.0, "text": "Его жену, мою прабабушку, звали Мария."},
        {"id": 3, "start": 12.4, "end": 16.0, "text": "Бауыржан – мой отец, әкем, родился в 1955 году."},
        {"id": 4, "start": 16.4, "end": 22.0, "text": "Дед всю жизнь дружил с соседом, его звали Олжас, но не родственник."},
        {"id": 5, "start": 22.4, "end": 26.0, "text": "У деда и Қарлыға родились сын Бауыржан и дочь Гүлнар."},
    ],
}


def rel(a, r, b, seg, quote):
    return verify_relation({"a": a, "rel": r, "b": b, "seg": seg, "quote": quote}, T)


def test_verified_with_narrator_pronoun():
    out = rel("Бауыржан", "father", "Нұрлан", 3, "Бауыржан – мой отец")
    assert out["status"] == "verified", out
    assert out["evidence"]["start"] == 12.4


def test_kazakh_kinship_word():
    out = rel("Бауыржан", "father", "Нұрлан", 3, "әкем")
    # quote is found and the segment has both people and a kinship word
    assert out["status"] == "verified", out


def test_case_ending_still_matches():
    out = rel("Бауыржан", "son", "Қарлыға", 5, "У деда и Қарлыға родились сын Бауыржан")
    assert out["status"] == "verified", out


def test_invented_person_is_ghost():
    out = rel("Ербол", "brother", "Бауыржан", 3, "Бауыржан – мой отец")
    assert out["status"] == "ghost" and out["reason"] == "invented_person"


def test_quote_not_in_recording():
    out = rel("Сәкен", "father", "Бауыржан", 1, "Сәкен был отцом Бауыржана")
    assert out["reason"] == "quote_not_found"


def test_neighbour_is_not_a_relative():
    out = rel("Олжас", "brother", "Нұрлан", 4, "его звали Олжас")
    assert out["status"] == "ghost"
    assert out["reason"] in ("no_kinship_word", "name_not_in_quote")


def test_name_in_previous_sentence():
    out = rel("Мария", "wife", "Сәкен", 2, "Его жену, мою прабабушку, звали Мария")
    # "его" points to Сәкен one sentence earlier: accepted, evidence spans both
    assert out["status"] == "verified", out
    assert out["evidence"]["start"] == 5.4 and "previous" in out["context"]


def test_name_two_sentences_back_is_not_enough():
    out = rel("Нұрлан", "son", "Мария", 3, "Бауыржан – мой отец")
    assert out["status"] == "ghost"


def test_tree_keeps_ghosts_separate():
    ext = {"relations": [
        {"a": "Бауыржан", "rel": "father", "b": "Нұрлан", "seg": 3, "quote": "Бауыржан – мой отец"},
        {"a": "Ербол", "rel": "brother", "b": "Бауыржан", "seg": 3, "quote": "мой отец"},
    ], "facts": [
        {"person": "Бауыржан", "kind": "born", "value": "1955", "seg": 3, "quote": "родился в 1955 году"},
        {"person": "Сәкен", "kind": "born", "value": "1898", "seg": 1, "quote": "родился в 1897 году"},
    ]}
    v = verify(ext, T)
    assert [f["status"] for f in v["facts"]] == ["verified", "ghost"]
    tree = build(v, narrator="Нұрлан")
    ghosts = [e for e in tree["edges"] if e["ghost"]]
    assert len(ghosts) == 1 and ghosts[0]["reason"] == "invented_person"
    assert tree["generations_up"] == 1
