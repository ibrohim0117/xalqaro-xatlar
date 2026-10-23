"""B5.3b: sana — bir necha OCR o'qigan matndan ovoz berish (o'lchov ham, prototip ham shu koddan).

Har OCR o'z bo'laklaridan (date, line, header) sana nomzodlarini beradi; har OCR o'zi topgan sanalar
TO'PLAMI bilan bitta ovoz beradi. Qoida (dev 70, B5.3b-6, oyna 365):
  - "biri topadi, boshqasi tasdiqlaydi" (confirmed): 1-OCR (VLM) sanasi, boshqa OCR ko'rgan bo'lsa —
    28 tadan 27 to'g'ri: shuning uchun avtomatik EMAS, "tekshiring" belgisi bilan yoziladi;
  - takliflar (ranked): ko'proq OCR ko'rgan 3 ta sana;
  - oyna (in_window): sana kelgan kundan oldin va ko'pi bilan 365 kun oldin (dev'da 9..97 kun) —
    xato o'qilgan yil ("2015") chetlanadi.
"""

import re
from collections import Counter
from datetime import date as Date

from src.fields.date_number import all_dates, parse_date

ANCHOR_TOKEN = re.compile(r"№|\bN[oо°º]?\b", re.IGNORECASE)  # OCR: "№", "No", "N", "N°"
STRONG = ("date", "header_anchor")  # ishonchli bo'laklar
WINDOW_DAYS = 365  # dev: kirish_sana - hujjat_sana = 9..97 kun; zaxira bilan


def header_anchor_date(text: str) -> str | None:
    """header matnida "№" (No/N) bor qatordagi sana — "от" dan keyingisi emas."""
    for line in text.splitlines():
        date = next((d for d, ot in all_dates(line) if not ot), None)
        if date and ANCHOR_TOKEN.search(line):
            return date
    return None


def engine_dates(texts: dict[str, str]) -> dict[str, str | None]:
    """Bitta OCR'ning bo'laklaridan sana nomzodlari."""
    header = texts.get("header", "")
    return {
        "date": parse_date(texts.get("date", "")),
        "line": parse_date(texts.get("line", ""), skip_after_ot=True),
        "header_anchor": header_anchor_date(header),
        "header_first": next((d for d, ot in all_dates(header) if not ot), None),
    }


def vote(per_engine: list[set[str]], min_votes: int = 2) -> str | None:
    """Kamida min_votes ta OCR ko'rgan sana; teng bo'lsa — hech biri (ishonchsiz)."""
    counts = Counter(d for dates in per_engine for d in dates)
    ranked = counts.most_common(2)
    if not ranked or ranked[0][1] < min_votes:
        return None
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        return None
    return ranked[0][0]


def confirmed(
    found: list[dict[str, str | None]], min_others: int = 1, keys: tuple[str, ...] | None = None
) -> str | None:
    """1-OCR'ning sanasi — boshqa OCR'lardan kamida min_others tasi uni ko'rgan bo'lsa
    (keys berilsa — faqat shu bo'laklarda)."""
    first = found[0]["date"] or found[0]["header_anchor"]
    if not first:
        return None
    seen = sum(first in {v for k, v in f.items() if keys is None or k in keys} for f in found[1:])
    return first if seen >= min_others else None


def ranked(per_engine: list[set[str]], k: int = 3) -> list[str]:
    """Takliflar: ko'proq OCR ko'rgan sana oldinda, ko'pi bilan k ta."""
    counts = Counter(d for dates in per_engine for d in dates)
    return [date for date, _ in counts.most_common(k)]


def to_day(value: str | None) -> Date | None:
    """ "DD.MM.YYYY" -> sana (noto'g'ri bo'lsa None)."""
    try:
        day, month, year = (int(x) for x in (value or "").split("."))
        return Date(year, month, day)
    except ValueError:
        return None


def in_window(value: str | None, received: Date | None, days: int | None) -> bool:
    """Sana kelgan kundan oldin va ko'pi bilan days kun oldin bo'lsa (yoki tekshiruv o'chiq)."""
    if days is None or received is None or value is None:
        return value is not None
    day = to_day(value)
    return day is not None and 0 <= (received - day).days <= days


def windowed(
    found: dict[str, str | None], received: Date | None, days: int | None = WINDOW_DAYS
) -> dict[str, str | None]:
    """Nomzodlardan oynadan tashqaridagilarni olib tashlaydi (None qiladi)."""
    return {k: (v if in_window(v, received, days) else None) for k, v in found.items()}
