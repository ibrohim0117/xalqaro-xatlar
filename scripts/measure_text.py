"""B3.3: matn qatlami va OCR sifatini real dev xatlarda o'lchash. Ekranga FAQAT raqamlar chiqadi.

Savol: json'dagi to'g'ri sana va raqam xat matnining ichida bormi? Bu B5 uchun yuqori chegara —
matnda yo'q qiymatni matndan qidiradigan hech qanday qoida topa olmaydi.

Ishga tushirish:
    poetry run python -m scripts.measure_text             # 70 dev xat, 2 sahifa (~6 daqiqa, OCR)
    poetry run python -m scripts.measure_text --limit 5   # tez sinov
"""

import argparse
import re
import statistics
import sys
import time
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from src.dataset import list_letters, load_split, load_truth
from src.evaluate import normalize, true_values
from src.pdf_text import PageText, has_text_layer, read_ocr, read_text_layer

LOW_CONF = 60  # shundan past ishonchli so'z "shubhali" hisoblanadi
FUZZY_MIN = 85  # "deyarli topildi": 1-2 belgi farq
MONTH_STEMS = [
    "янв",
    "фев",
    "мар",
    "апр",
    "ма[йя]",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
]


def number_found(value: str, text: str, fuzzy: bool = False) -> bool:
    """Raqam matnda bormi (bo'shliq va chiziq turi hisobga olinmaydi)."""
    needle, haystack = normalize(value, spaceless=True), normalize(text, spaceless=True)
    if not needle:
        return False
    if fuzzy:
        return fuzz.partial_ratio(needle, haystack) >= FUZZY_MIN
    return needle in haystack


def date_found(value: str, text: str) -> bool:
    """json'dagi "DD.MM.YYYY" sana matnda biror ko'rinishda bormi:
    05.12.2025, 5.12.25, 05/12/2025, 5 декабря 2025, 05 ДЕК 2025."""
    try:
        day, month, year = (int(part) for part in value.split("."))
    except (ValueError, AttributeError):
        return False
    low = normalize(text)
    sep = r"\s*[.,/-]\s*"
    numeric = rf"(?<!\d)0?{day}{sep}0?{month}{sep}(?:{year}|{year % 100:02d})(?!\d)"
    words = rf"(?<!\d)0?{day}\s*{MONTH_STEMS[month - 1]}[а-яё]*\.?\s*{year}(?!\d)"
    return bool(re.search(numeric, low) or re.search(words, low))


def anchor_y(pages: list[PageText]) -> float | None:
    """1-sahifaning yuqori yarmidagi eng yuqori "№" belgisining joyi (y) — sana-raqam qatori.
    Pastroqdagi ikkinchi "№" odatda "На № ___ от ___" qatori."""
    ys = [w.y0 for p in pages if p.number == 1 for w in p.words if "№" in w.text and w.y0 < 0.5]
    return min(ys) if ys else None


def joined(pages: list[PageText]) -> str:
    return "\n".join(page.text for page in pages)


@dataclass
class SourceStats:
    """Bitta o'qish yo'li bo'yicha hisob."""

    letters: int = 0
    pages: int = 0
    seconds: float = 0.0
    number_exact: int = 0
    number_fuzzy: int = 0
    date: int = 0
    anchors: list[float] = field(default_factory=list)  # topilgan "№" langarlarining y joyi
    confs: list[float] = field(default_factory=list)

    def add(self, pages: list[PageText], truth: dict) -> None:
        text = joined(pages)
        self.letters += 1
        self.number_exact += number_found(truth["hujjat_raqami"], text)
        self.number_fuzzy += number_found(truth["hujjat_raqami"], text, fuzzy=True)
        self.date += date_found(truth["hujjat_sana"], text)
        if (y := anchor_y(pages)) is not None:
            self.anchors.append(y)
        for page in pages:
            self.confs += [w.conf for w in page.words if w.conf is not None]


def pct(part: int, whole: int) -> str:
    return f"{part:>2}/{whole:<2} {part / whole:4.0%}" if whole else "     —     "


def main() -> None:
    parser = argparse.ArgumentParser(description="Matn qatlami va OCR sifatini o'lchash (dev)")
    parser.add_argument("--pages", type=int, default=2, help="har xatdan nechta sahifa")
    parser.add_argument("--limit", type=int, default=None, help="faqat dastlabki N xat (sinov)")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    doc_ids = load_split()["dev"][: args.limit]
    text_layer, ocr, rule, either = SourceStats(), SourceStats(), SourceStats(), SourceStats()

    for n, doc_id in enumerate(doc_ids, 1):
        print(f"\r  o'qilmoqda: {n}/{len(doc_ids)}", end="", file=sys.stderr, flush=True)
        letter, truth = letters[doc_id], true_values(load_truth(letters[doc_id]))

        started = time.perf_counter()
        tl_pages = read_text_layer(letter.pdf, args.pages)
        text_layer.seconds += time.perf_counter() - started
        started = time.perf_counter()
        ocr_pages = read_ocr(letter.pdf, args.pages)
        ocr.seconds += time.perf_counter() - started
        ocr.pages += len(ocr_pages)

        if any(has_text_layer(page.words) for page in tl_pages):
            text_layer.pages += len(tl_pages)
            text_layer.add(tl_pages, truth)
        ocr.add(ocr_pages, truth)
        # read_pdf qoidasi: har sahifada matn qatlami bo'lsa o'sha, bo'lmasa OCR
        chosen = [
            t if has_text_layer(t.words) else o for t, o in zip(tl_pages, ocr_pages, strict=True)
        ]
        rule.add(chosen, truth)
        either.add(tl_pages + ocr_pages, truth)
    print(file=sys.stderr)

    n = len(doc_ids)
    print(f"B3.3: dev {n} xat, har biridan {args.pages} sahifa\n")
    columns = [("matn qatlami", text_layer), ("OCR", ocr), ("read_pdf", rule), ("ikkalasi", either)]
    print(f"  {'':<22}" + "".join(f"{name:>14}" for name, _ in columns))
    rows = [
        ("matnli xatlar", lambda s: pct(s.letters, n)),
        ("raqam aniq topildi", lambda s: pct(s.number_exact, s.letters)),
        ("raqam deyarli topildi", lambda s: pct(s.number_fuzzy, s.letters)),
        ("sana topildi", lambda s: pct(s.date, s.letters)),
        ("№ langari (1-sahifa)", lambda s: pct(len(s.anchors), s.letters)),
    ]
    for label, cell in rows:
        print(f"  {label:<22}" + "".join(f"{cell(s):>14}" for _, s in columns))

    print("\n  № joyi, y (0 = sahifa tepasi, 1 = pasti):")
    for name, stats in columns[:2]:
        if stats.anchors:
            ys = stats.anchors
            print(
                f"    {name:<13} median {statistics.median(ys):.2f}"
                f" | min {min(ys):.2f} | max {max(ys):.2f}"
            )

    confs = ocr.confs
    low = sum(c < LOW_CONF for c in confs)
    print("\n  OCR:")
    print(f"    o'rtacha ishonch: {statistics.mean(confs):.0f}" if confs else "    so'z yo'q")
    if confs:
        print(f"    ishonchi < {LOW_CONF} so'zlar: {low}/{len(confs)} ({low / len(confs):.0%})")
    if ocr.pages:
        print(
            f"    vaqt: {ocr.seconds / ocr.pages:.1f} s/sahifa (jami {ocr.seconds / 60:.1f} daqiqa)"
        )
    if text_layer.pages:
        per_page = text_layer.seconds / max(n * args.pages, 1)
        print(f"  Matn qatlami: {per_page:.3f} s/sahifa")


if __name__ == "__main__":
    main()
