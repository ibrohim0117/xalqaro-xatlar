"""B5.3b: berilgan xatlarda OCR o'qigan sana to'g'ri sanadan QANDAY farq qiladi — qiymatlarsiz.

Har OCR va har bo'lak uchun munosabat chiqadi:
  to'g'ri / kun farq / oy farq / yil farq / bir nechta qism farq (raqam noto'g'ri o'qilgan) /
  "от" dan keyingi sana (xatdagi boshqa sana olingan) / sana o'qilmadi.
Shu bilan "OCR raqamni xato o'qidimi" yoki "xatdagi boshqa sanani oldimi" ajraladi.
MAXFIYLIK: sanalarning o'zi ekranga CHIQMAYDI — faqat munosabat.

Ishga tushirish:
    poetry run python -m scripts.ocr.explain_dates DOC_1 DOC_2 --readers vlm rapidocr rapidocr-eslav
"""

import argparse
import json

from scripts.ocr.compare_ocr import OUT_DIR
from src.evaluation.dataset import list_letters, load_truth
from src.fields.date_number import all_dates

CROPS = ("date", "line", "header")
PARTS = ("kun", "oy", "yil")


def relation(text: str, truth: str) -> str:
    """OCR matnidagi sanalar to'g'ri sanaga nisbatan qanday."""
    dates = all_dates(text)
    if not dates:
        return "sana o'qilmadi"
    if any(date == truth for date, _ in dates):
        where = "'от' dan keyin" if all(ot for d, ot in dates if d == truth) else "to'g'ri"
        return where if len(dates) == 1 else f"{where} (+{len(dates) - 1} boshqa sana)"
    first, ot = next(((d, ot) for d, ot in dates if not ot), dates[0])
    if ot:
        return "faqat 'от' dan keyingi boshqa sana"
    differ = [
        p for p, a, b in zip(PARTS, first.split("."), truth.split("."), strict=True) if a != b
    ]
    return f"{' va '.join(differ)} farq" if len(differ) < 3 else "butunlay boshqa sana"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docs", nargs="+")
    parser.add_argument("--readers", nargs="+", default=["vlm", "rapidocr", "rapidocr-eslav"])
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    texts = {
        r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in args.readers
    }
    for doc_id in args.docs:
        truth = (load_truth(letters[doc_id]).get("rekvizit_document") or {}).get("hujjat_sana")
        print(f"{doc_id}:")
        for reader in args.readers:
            read = texts[reader].get(doc_id, {})
            cells = [f"{crop}: {relation(read[crop], truth)}" for crop in CROPS if crop in read]
            print(f"  {reader:<16} " + " | ".join(cells))


if __name__ == "__main__":
    main()
