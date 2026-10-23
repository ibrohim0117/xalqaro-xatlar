"""Umumiy matn yordamchilari: solishtirish uchun tekislash, eng ko'p qiymat, kirilldan lotinga.

Hamma qatlam (maydon qoidalari, model, baholash) shu yerdan oladi — ular bir-biriga bog'lanmaydi.
"""

import re
import unicodedata
from collections import Counter

APOSTROPHES = re.compile(r"[\u2018\u2019\u02bb\u02bc\u02b9`\u00b4]")  # ‘ ’ ʻ ʼ ʹ ` ´
DASHES = re.compile(r"[\u2010-\u2015\u2212]")  # ‐ ‑ ‒ – — ― −


def normalize(value: str | None, spaceless: bool = False) -> str:
    """Faqat solishtirish uchun: ma'noga ta'sir qilmaydigan farqlarni tekislaydi."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value)).lower()
    text = APOSTROPHES.sub("'", text)
    text = DASHES.sub("-", text)
    text = re.sub(r"\s+", "" if spaceless else " ", text)
    return text.strip(" .,;:")


def most_common(values: list[str | None], spaceless: bool = False) -> tuple[str | None, int]:
    """Eng ko'p uchragan qiymat va u necha marta uchragani.

    Tekislangan holda sanaladi: "O.N. Xrushev" va "O.N.Xrushev" bitta qiymat.
    """
    filled = [v for v in values if v]
    if not filled:
        return None, 0
    counts = Counter(normalize(v, spaceless) for v in filled)
    key, n = counts.most_common(1)[0]
    original = next(v for v in filled if normalize(v, spaceless) == key)
    return original, n


# Rus va o'zbek kirill harflari -> o'zbek lotin yozuvi (rus ismlarini o'zbekcha yozish odati)
CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}  # fmt: skip
VOWELS = set("аеёиоуыэюяў")


def to_latin(word: str) -> str:
    """Kirill so'zni lotinga o'giradi. So'z boshida va unlidan keyin "Е" -> "Ye" (Евгений)."""
    out = []
    for i, ch in enumerate(word):
        low = ch.lower()
        if low == "е" and (i == 0 or word[i - 1].lower() in VOWELS):
            latin = "ye"
        else:
            latin = CYR2LAT.get(low, ch)
        out.append(latin.capitalize() if ch.isupper() and latin else latin)
    return "".join(out)
