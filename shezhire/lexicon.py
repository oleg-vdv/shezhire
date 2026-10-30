"""Kinship words in Russian, Kazakh and English.

The verifier does not trust the relation the model reports. It accepts a
relation only if the quoted words contain a kinship word from the same group.
Matching is by token prefix, so Kazakh suffixes (әкесі, әкемнің) and Russian
case endings (отца, отцом) still match.
"""

# relation the model may report -> group of words that can support it
GROUP_OF = {
    "father": "parent",
    "mother": "parent",
    "son": "parent",
    "daughter": "parent",
    "husband": "spouse",
    "wife": "spouse",
    "brother": "sibling",
    "sister": "sibling",
    "grandfather": "grandparent",
    "grandmother": "grandparent",
}

STEMS = {
    "parent": [
        # ru
        "отец", "отц", "пап", "мать", "матер", "мам", "сын", "дочь", "дочер",
        "родил", "родила", "родител", "дет", "ребен", "ребён",
        # kk
        "әке", "көке", "ана", "шеше", "ұл", "қыз", "перзент", "бала",
        # en
        "father", "dad", "mother", "mom", "son", "daughter", "born to", "parent",
    ],
    "spouse": [
        "муж", "жен", "супруг", "вышла замуж", "замуж",
        "күйеу", "әйел", "жұбай", "үйленді", "тұрмысқа",
        "husband", "wife", "married",
    ],
    "sibling": [
        "брат", "сестр", "двое детей", "трое детей", "дет",
        "аға", "іні", "бауыр", "әпке", "апа", "қарындас", "сіңлі",
        "brother", "sister", "sibling",
    ],
    "grandparent": [
        "дед", "бабушк", "баб", "внук", "внучк",
        "ата", "әже", "немере",
        "grandfather", "grandmother", "grandson", "granddaughter", "grandpa", "grandma",
    ],
}

# how a reported relation turns into a tree edge: (edge kind, a is ..., direction)
# "parent" edges always point parent -> child
EDGE = {
    "father": ("parent", "a_parent"),
    "mother": ("parent", "a_parent"),
    "son": ("parent", "b_parent"),
    "daughter": ("parent", "b_parent"),
    "husband": ("spouse", None),
    "wife": ("spouse", None),
    "brother": ("sibling", None),
    "sister": ("sibling", None),
    "grandfather": ("grandparent", "a_parent"),
    "grandmother": ("grandparent", "a_parent"),
}

FIRST_PERSON = [
    "я", "мой", "моя", "мое", "моё", "мои", "моего", "моей", "моих", "меня", "мне", "мы", "наш", "наша",
    "мен", "менің", "маған", "мені", "біз", "біздің",
    "i", "my", "me", "we", "our",
]
