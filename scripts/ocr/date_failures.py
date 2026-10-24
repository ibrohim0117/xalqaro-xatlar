"""Sana: to'g'ri yozilmagan xatlarda nima bo'lyapti — VLM o'qimadimi, xato o'qidimi, biz noto'g'ri
sanani tanladikmi yoki "№" qatori yo'qmi. OCR qayta ishlatilmaydi (outputs/ocr/*.json dan).

Har dev xat prototip qoidasi bilan (matn qatlami -> auto; VLM + tasdiq -> ⚠; 3 taklif; oyna 365)
to'rt holatdan biriga tushadi: yozildi to'g'ri / yozildi xato / faqat takliflarda / topilmadi.
To'g'ri yozilmaganlarda — VLM har bo'lakda to'g'ri sanaga nisbatan qanday (explain_dates.relation).
Ekranga FAQAT sonlar chiqadi; --ids — "topilmadi" xatlarning DOC raqamlari (qo'lda ko'rish uchun).

Ishga tushirish: poetry run python -m scripts.ocr.date_failures [--ids]
"""

import argparse
import json
from collections import Counter, defaultdict

from scripts.ocr.compare_ocr import OUT_DIR
from scripts.ocr.explain_dates import relation
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number
from src.fields.date_vote import (
    WINDOW_DAYS,
    confirmed,
    engine_dates,
    in_window,
    ranked,
    to_day,
    windowed,
)

READERS = ["vlm", "rapidocr", "rapidocr-eslav", "tesseract-block"]  # VLM birinchi (prototip kabi)
CROPS = ("date", "line", "header")
OUTCOMES = ("yozildi to'g'ri", "yozildi xato", "faqat takliflarda", "topilmadi")


def outcome(texts: list[dict[str, str]], text_layer: str | None, truth: str, received) -> str:
    """Prototip qoidasi bilan bu xatda sana qaysi holatga tushadi."""
    if in_window(text_layer, received, WINDOW_DAYS):
        return "yozildi to'g'ri" if text_layer == truth else "yozildi xato"
    found = [windowed(engine_dates(t), received) for t in texts]
    if prefill := confirmed(found):
        return "yozildi to'g'ri" if prefill == truth else "yozildi xato"
    return (
        "faqat takliflarda"
        if truth in ranked([{d for d in f.values() if d} for f in found])
        else "topilmadi"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="topilmagan xatlarning DOC raqamlari")
    args = parser.parse_args()
    letters = {letter.doc_id: letter for letter in list_letters()}
    missing = defaultdict(list)  # (VLM header'da nima, "№" bormi) -> DOC raqamlari
    dev = sorted(load_split()["dev"])
    saved = {r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in READERS}
    cases, anchors, vlm = Counter(), Counter(), Counter()
    for doc_id in dev:
        document = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        truth, received = document.get("hujjat_sana"), to_day(document.get("kirish_sana"))
        first = get_pages(letters[doc_id])[0]
        texts = [saved[r].get(doc_id, {}) for r in READERS]
        text_layer = date_and_number(first.text_layer)[0]
        case = outcome(texts, text_layer, truth, received)
        cases[case] += 1
        if case.startswith("yozildi"):
            continue
        has_anchor = "line" in texts[0]  # bo'laklar "№" langari topilganda kesilgan (make_crops)
        anchors[case, "bor" if has_anchor else "yo'q"] += 1
        for crop in CROPS:
            kind = relation(texts[0][crop], truth) if crop in texts[0] else "bo'lak yo'q"
            vlm[case, crop, kind.split(" (+")[0]] += 1
        if case == "topilmadi":
            header = relation(texts[0].get("header", ""), truth).split(" (+")[0]
            missing[header, "'№' bor" if has_anchor else "'№' yo'q"].append(doc_id)

    print(f"Sana: to'g'ri yozilmagan xatlar tahlili, dev {len(dev)} xat\n")
    for case in OUTCOMES:
        extra = ""
        if not case.startswith("yozildi"):
            extra = f"   ('№' qatori bor {anchors[case, 'bor']}, yo'q {anchors[case, "yo'q"]})"
        print(f"  {case:<20} {cases[case]:>3}{extra}")
    kinds = sorted({k for (_, _, k) in vlm})
    for case in ("faqat takliflarda", "topilmadi"):
        print(f"\n  {case} ({cases[case]} xat) — VLM har bo'lakda:")
        for crop in CROPS:
            row = ", ".join(f"{k} {vlm[case, crop, k]}" for k in kinds if vlm[case, crop, k])
            print(f"    {crop:<7} {row}")

    if args.ids:
        print("\n  Topilmagan xatlar (VLM header'da nima ko'rgan, \"№\" qatori):")
        for (header, anchor), docs in sorted(missing.items()):
            print(f"    {header}, {anchor} ({len(docs)}): {', '.join(docs)}")


if __name__ == "__main__":
    main()
