"""B5.3b-3: sana — bir necha OCR natijasini birlashtirish ("ovoz berish"). OCR qayta ishlatilmaydi.

compare_ocr saqlagan matnlar (outputs/ocr/<OCR>.json) va matn qatlamidagi sana asosida:
  S0  hozirgi: faqat matn qatlami;
  S1  matn qatlami, bo'lmasa 1-OCR'ning date bo'lagi;
  S2  matn qatlami, bo'lmasa date bo'laklaridan kamida 2 OCR kelishgan sana;
  S3  S2 + header'dagi "№" qatori sanasi ham ovozga kiradi (RapidOCR "№" ni "No"/"N" deb o'qiydi);
  S4  S3 + line bo'lagi va header'dagi birinchi sana ham (ko'proq javob, kamroq ishonch).
Har OCR o'zi topgan sanalar TO'PLAMI bilan bitta ovoz beradi (bir OCR ikki bo'lakdan bir xil sana
o'qisa — bitta ovoz). Avtomatik javob bo'lmagan xatlarga taklif: eng ko'p OCR ko'rgan sana;
"3 ichida" — to'g'ri sana ovoz bo'yicha eng yuqori 3 ta taklif orasidami (xodim tanlaydi).
Ekranga FAQAT sonlar chiqadi.

Avval: poetry run python -m scripts.ocr.compare_ocr rapidocr rapidocr-eslav tesseract-block
Keyin: poetry run python -m scripts.ocr.combine_dates rapidocr rapidocr-eslav tesseract-block
"""

import argparse
import json
import re
from collections import Counter

from scripts.ocr.compare_ocr import OUT_DIR
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import all_dates, date_and_number, parse_date

ANCHOR_TOKEN = re.compile(r"№|\bN[oо°º]?\b", re.IGNORECASE)  # OCR: "№", "No", "N", "N°"
SOURCES = {  # strategiya -> har OCR'dan qaysi sanalar ovozga kiradi
    "S2 date bo'laklari": ("date",),
    "S3 + header '№' qatori": ("date", "header_anchor"),
    "S4 + line, header birinchi": ("date", "header_anchor", "line", "header_first"),
}


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


def ranked(per_engine: list[set[str]], k: int = 3) -> list[str]:
    """Takliflar: ko'proq OCR ko'rgan sana oldinda, ko'pi bilan k ta."""
    counts = Counter(d for dates in per_engine for d in dates)
    return [date for date, _ in counts.most_common(k)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readers", nargs="+", help="compare_ocr saqlagan OCR nomlari")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    texts = {
        r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in args.readers
    }
    stats = Counter()  # (strategiya, "auto" | "auto_ok" | "hint" | "hint_ok")
    for doc_id in dev:
        truth = (load_truth(letters[doc_id]).get("rekvizit_document") or {}).get("hujjat_sana")
        text_layer = date_and_number(get_pages(letters[doc_id])[0].text_layer)[0]
        found = [engine_dates(texts[r].get(doc_id, {})) for r in args.readers]
        auto = {
            "S0 hozirgi (matn qatlami)": text_layer,
            "S1 + 1-OCR date bo'lagi": text_layer or found[0]["date"],
        }
        for name, keys in SOURCES.items():
            auto[name] = text_layer or vote([{f[k] for k in keys if f[k]} for f in found])
        everything = [{d for d in f.values() if d} for f in found]
        hint = vote(everything, min_votes=1)
        top3 = ranked(everything)
        for name, value in auto.items():
            if value:
                stats[name, "auto"] += 1
                stats[name, "auto_ok"] += value == truth
            elif top3:
                stats[name, "hint"] += bool(hint)
                stats[name, "hint_ok"] += hint == truth
                stats[name, "top3_ok"] += truth in top3

    print(
        f"Sana: OCR'larni birlashtirish, dev {len(dev)} xat; OCR'lar: {', '.join(args.readers)}\n"
    )
    head = f"{'avtomatik':>10}{'to`g`ri':>9}{'xato':>6}{'taklif':>9}{'to`g`ri':>9}{'3 ichida':>10}"
    print(f"  {'strategiya':<30}{head}")
    for name in ["S0 hozirgi (matn qatlami)", "S1 + 1-OCR date bo'lagi", *SOURCES]:
        auto_n, ok = stats[name, "auto"], stats[name, "auto_ok"]
        hints = f"{stats[name, 'hint']:>9}{stats[name, 'hint_ok']:>9}{stats[name, 'top3_ok']:>10}"
        print(f"  {name:<30}{auto_n:>10}{ok:>9}{auto_n - ok:>6}{hints}")


if __name__ == "__main__":
    main()
