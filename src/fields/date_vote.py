"""B5.3b: sana — bir necha OCR o'qigan matndan ovoz berish (o'lchov ham, prototip ham shu koddan).

Har OCR o'z bo'laklaridan (date, line, header, page) sana nomzodlarini beradi; har OCR o'zi topgan
sanalar TO'PLAMI bilan bitta ovoz beradi. Qoida (dev 70, oyna 365):
  - "biri topadi, boshqasi tasdiqlaydi" (prefill_date): topuvchi OCR (FINDERS) sanasi, boshqa OCR
    ko'rgan bo'lsa. VLM aniq savol bilan (B5.3c-8, X2): 34 tadan 32 to'g'ri; VLM ko'chirish
    (B5.3b-6): 28 tadan 27. Shuning uchun avtomatik EMAS, "tekshiring" belgisi bilan yoziladi;
  - 27.10 ziddiyat (rival_dates, C varianti): kamida 2 MUSTAQIL OCR (topuvchi bilan bir model emas)
    boshqa sanaga kelishgan va u yozilajak sanadan ko'p ovoz olgan bo'lsa — yozilmaydi, faqat
    takliflar. Sabab: Кызмат blankida VLM'ning ikki savoli bir xil xato kun berib, bir-birini
    "tasdiqlagan", RapidOCR va Apple Vision esa to'g'ri o'qigan. O'lchov (compare_date_rules):
    yangi 25 — xato yozilgan 3 -> 0, to'g'ri 18 -> 18; dev 70 — to'g'ri 54 -> 50 (4 tasi bo'sh
    qoladi, to'g'risi takliflarda), xato 2 -> 2; bir bosishda o'zgarmadi (63/70, 22/25),
    "to'g'ri -> xato" 0.
    Ziddiyatda mustaqillar sanasini yozish (D) rad etildi: dev'da 4 ta to'g'ri -> xato;
  - takliflar (ranked): ko'proq OCR ko'rgan 3 ta sana;
  - oyna (in_window): sana kelgan kundan oldin va ko'pi bilan 365 kun oldin (dev'da 9..97 kun);
  - B5.11 yil tuzatish (fix_year): oynadan tashqaridagi sanada kun va oy o'sha qoladi, yil —
    oynaga tushadigani ("12.03.2016" -> "12.03.2026"). VLM ko'p xatoni yilda qiladi: dev'da
    to'g'ri yozilgan 45 -> 53, xato 2 -> 2, bir bosishda 59 -> 62 (oyna 120 kun bo'lsa ham bir xil).
"""

import re
from collections import Counter
from datetime import date as Date

from src.fields.date_number import OCR_PATTERNS, all_dates, parse_date

ANCHOR_TOKEN = re.compile(r"№|\bN[oо°º]?\b", re.IGNORECASE)  # OCR: "№", "No", "N", "N°"
STRONG = ("date", "header_anchor")  # ishonchli bo'laklar
FIRST = STRONG  # 1-OCR'ning sanasi qaysi bo'laklardan olinadi (prototip qoidasi)
HEADER = ("header_anchor", "header_first")  # sahifa yuqorisidagi sana
WINDOW_DAYS = 365  # dev: kirish_sana - hujjat_sana = 9..97 kun; zaxira bilan


def header_anchor_date(text: str, patterns=OCR_PATTERNS) -> str | None:
    """header matnida "№" (No/N) bor qatordagi sana — "от" dan keyingisi emas."""
    for line in text.splitlines():
        date = next((d for d, ot in all_dates(line, patterns) if not ot), None)
        if date and ANCHOR_TOKEN.search(line):
            return date
    return None


def engine_dates(texts: dict[str, str], patterns=OCR_PATTERNS) -> dict[str, str | None]:
    """Bitta OCR'ning bo'laklaridan sana nomzodlari (patterns — o'lchovda solishtirish uchun)."""
    header = texts.get("header", "")
    return {
        "date": parse_date(texts.get("date", ""), patterns=patterns),
        "line": parse_date(texts.get("line", ""), skip_after_ot=True, patterns=patterns),
        "header_anchor": header_anchor_date(header, patterns),
        "header_first": next((d for d, ot in all_dates(header, patterns) if not ot), None),
        "page": parse_date(texts.get("page", ""), skip_after_ot=True, patterns=patterns),
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


def first_date(found: list[dict[str, str | None]], keys: tuple[str, ...] = FIRST) -> str | None:
    """1-OCR'ning sanasi: keys tartibida birinchi topilgan bo'lak."""
    return next((found[0][k] for k in keys if found[0][k]), None)


def confirmed(
    found: list[dict[str, str | None]],
    min_others: int = 1,
    keys: tuple[str, ...] | None = None,
    first_keys: tuple[str, ...] = FIRST,
) -> str | None:
    """1-OCR'ning sanasi (first_keys bo'laklaridan) — boshqa OCR'lardan kamida min_others tasi uni
    ko'rgan bo'lsa (keys berilsa — faqat shu bo'laklarda)."""
    first = first_date(found, first_keys)
    if not first:
        return None
    seen = sum(first in {v for k, v in f.items() if keys is None or k in keys} for f in found[1:])
    return first if seen >= min_others else None


# Topuvchi OCR -> uning sanasi qaysi bo'laklardan olinadi (keyin boshqa OCR tasdiqlashi kerak)
FINDERS = {
    "vlm-extract": HEADER,  # aniq savol: JSON'da "№" yo'q — header'dagi birinchi sana
    "vlm": FIRST,  # ko'chirish: date bo'lagi yoki header'dagi "№" qatori
}


RIVAL_MIN = 2  # kamida shuncha mustaqil OCR kelishgan boshqa sana — ziddiyat


def same_model(a: str, b: str) -> bool:
    """VLM'ning savollari (vlm-extract, vlm) — bitta model: bir-birining ovozi mustaqil emas."""
    return a.startswith("vlm") and b.startswith("vlm")


def rival_dates(
    found: list[dict[str, str | None]], readers: list[str], written: str
) -> list[tuple[str, int]]:
    """Mustaqil OCR'lar (topuvchi readers[0] bilan bir model emas) kelishgan BOSHQA sanalar: kamida
    RIVAL_MIN ovoz va yozilajak sanadan ko'p. (sana, ovoz) — ko'p ovozlisi oldinda, teng ovozda —
    OCR va bo'lak tartibi. Har OCR har sanaga bitta ovoz beradi (qaysi bo'lakda bo'lsa ham)."""
    votes, order = Counter(), {}
    for reader, candidates in zip(readers[1:], found[1:], strict=True):
        if same_model(reader, readers[0]):
            continue
        for day in dict.fromkeys(v for v in candidates.values() if v):
            votes[day] += 1
            order.setdefault(day, len(order))
    rivals = [d for d, n in votes.items() if d != written and n >= RIVAL_MIN and n > votes[written]]
    return [(d, votes[d]) for d in sorted(rivals, key=lambda d: (-votes[d], order[d]))]


def prefill_date(
    found: list[dict[str, str | None]], finder: str | None, readers: list[str] | None = None
) -> str | None:
    """ "Tekshiring" belgisi bilan yoziladigan sana. found[0] — finder (FINDERS'da bo'lsa): uning
    sanasi, boshqa OCR tasdiqlasa; aks holda (VLM yo'q) — date bo'laklaridan kamida 2 OCR kelishgan
    sana. readers (found bilan bir tartibda, 1-si — finder) berilsa — 27.10 ziddiyat qoidasi:
    mustaqil OCR'lar boshqa sanaga kelishgan bo'lsa, yozilmaydi (rival_dates). readers'siz — eski
    qoida (o'lchovlarda taqqoslash uchun)."""
    if finder in FINDERS:
        date = confirmed(found, first_keys=FINDERS[finder])
    else:
        date = vote([{f["date"]} - {None} for f in found])
    if date and readers and rival_dates(found, readers, date):
        return None
    return date


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


def fix_year(value: str | None, received: Date | None, days: int | None) -> str | None:
    """Oynadagi sana — o'zi. Oynadan tashqaridagisida yil tuzatiladi: kun va oy o'sha, yil — kelgan
    yil yoki undan oldingisi, oynaga tushadigan BITTASI; bunday yil bo'lmasa — None."""
    if in_window(value, received, days) or value is None:
        return value
    parts = value.split(".")
    if len(parts) != 3:
        return None
    options = [f"{parts[0]}.{parts[1]}.{year}" for year in (received.year, received.year - 1)]
    fits = [o for o in options if in_window(o, received, days)]
    return fits[0] if len(fits) == 1 else None


def windowed(
    found: dict[str, str | None], received: Date | None, days: int | None = WINDOW_DAYS
) -> dict[str, str | None]:
    """Nomzodlar oynaga solinadi: oynadagisi qoladi, tashqaridagisida yil tuzatiladi (fix_year),
    tuzatib bo'lmasa — None."""
    return {k: fix_year(v, received, days) for k, v in found.items()}


def self_confirmed(
    found: list[dict[str, str | None]],
    main: tuple[str, ...] = HEADER,
    others: tuple[str, ...] = ("date", "line"),
) -> str | None:
    """1-OCR ikkita TURLI bo'lakda bir xil sanani o'qigan bo'lsa (o'z-o'zini tasdiqlash):
    main bo'lagidagi sana (standart — sahifa yuqorisi) others bo'laklaridan birida ham bor."""
    date = first_date(found, main)
    return date if date and date in {found[0][k] for k in others} else None


def only_candidate(found: list[dict[str, str | None]]) -> str | None:
    """Barcha OCR'lar topgan sanalardan (oyna ichida) faqat BITTASI bo'lsa — raqobatchi yo'q."""
    dates = {d for f in found for d in f.values() if d}
    return dates.pop() if len(dates) == 1 else None
