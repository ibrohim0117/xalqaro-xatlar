"""B5.3b-2: OCR'larni kesilgan bo'laklarda solishtirish — sana va raqam json bilan.

Har OCR uchun (make_crops yasagan bo'laklar, faqat dev):
- date.png   -> sana;  number.png -> raqam;  line.png -> sana va raqam (to'liq qator);
- header.png -> sana ("№" topilmagan xatlarda ham bor): birinchi sana, "от" dan keyingisi emas;
- "yangi qoida" — hozirgi tizim (matn qatlamidan sana avtomatik) + bo'sh qolgan joyga bo'lak OCR'i.
Hisob 70 xatga nisbatan (bo'lagi yo'q xat — javob yo'q). Javob: OCR biror qiymat chiqardi;
to'g'ri: json bilan mos (bo'shliqsiz solishtiriladi). Vaqt — bitta bo'lakka (median).
O'qilgan matnlar outputs/ocr/<OCR>.json ga yoziladi (keyingi tahlil uchun; Claude OCHMAYDI).
Ekranga FAQAT sonlar chiqadi.

Ishga tushirish (OCR nomlari — src/reading/engines READERS):
    poetry run python -m scripts.ocr.compare_ocr rapidocr rapidocr-eslav tesseract-block
"""

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path

from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import (
    OCR_PATTERNS,
    all_dates,
    date_and_number,
    parse_date,
    parse_number,
)
from src.reading.engines import READERS, make_reader

CROPS_DIR = Path("outputs/crops")
OUT_DIR = Path("outputs/ocr")
ROWS = [  # (qator nomi, maydon)
    ("sana: date bo'lagi", "sana"),
    ("sana: line bo'lagi", "sana"),
    ("sana: yangi qoida", "sana"),
    ("sana: header bo'lagi", "sana"),
    ("sana: yangi qoida + header", "sana"),
    ("raqam: number bo'lagi", "raqam"),
    ("raqam: line bo'lagi", "raqam"),
]


def same(value: str | None, expected: str | None) -> bool:
    return bool(value) and normalize(value, spaceless=True) == normalize(expected, spaceless=True)


def answers(texts: dict[str, str], text_layer_date: str | None) -> dict[str, str | None]:
    """Bo'laklardan o'qilgan matn -> har qator uchun qiymat."""
    date_crop = parse_date(texts.get("date", ""), patterns=OCR_PATTERNS)
    header = next((d for d, ot in all_dates(texts.get("header", ""), OCR_PATTERNS) if not ot), None)
    return {
        "sana: date bo'lagi": date_crop,
        "sana: line bo'lagi": parse_date(
            texts.get("line", ""), skip_after_ot=True, patterns=OCR_PATTERNS
        ),
        "sana: yangi qoida": text_layer_date or date_crop,
        "sana: header bo'lagi": header,
        "sana: yangi qoida + header": text_layer_date or date_crop or header,
        "raqam: number bo'lagi": parse_number(texts.get("number", "")),
        "raqam: line bo'lagi": parse_number(texts.get("line", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readers", nargs="+", choices=sorted(READERS))
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    truths = {d: load_truth(letters[d]).get("rekvizit_document") or {} for d in dev}
    expected = {
        d: {"sana": t.get("hujjat_sana"), "raqam": t.get("hujjat_raqami")}
        for d, t in truths.items()
    }
    # hozirgi tizim: sana matn qatlamidan avtomatik (B5.3: 13/13 to'g'ri)
    text_layer_dates = {d: date_and_number(get_pages(letters[d])[0].text_layer)[0] for d in dev}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n = len(dev)
    with_crops = sum((CROPS_DIR / d / "line.png").exists() for d in dev)
    now = sum(same(text_layer_dates[d], expected[d]["sana"]) for d in dev)
    print(f"B5.3b-2: OCR bo'laklarda, dev {n} xat ('sana № raqam' bo'lagi bor: {with_crops})")
    print(f"  hozirgi tizim: sana {now}/{n} (matn qatlamidan), raqam 0/{n} (faqat taklif)\n")
    for name in args.readers:
        reader = make_reader(name)
        stats, times, read = Counter(), [], {}
        for number, doc_id in enumerate(dev, 1):
            print(f"\r  {name}: {number}/{n} xat o'qilyapti…", end="", flush=True)
            folder = CROPS_DIR / doc_id
            texts = {}
            for crop in ("date", "number", "line", "header"):
                path = folder / f"{crop}.png"
                if path.exists():
                    start = time.perf_counter()
                    texts[crop] = reader.read(path.read_bytes())
                    times.append(time.perf_counter() - start)
            read[doc_id] = texts
            for row, value in answers(texts, text_layer_dates[doc_id]).items():
                if value:
                    stats[row, "javob"] += 1
                    stats[row, "to'g'ri"] += same(value, expected[doc_id][dict(ROWS)[row]])
        (OUT_DIR / f"{name}.json").write_text(json.dumps(read, ensure_ascii=False, indent=1))

        median = statistics.median(times) * 1000 if times else 0
        print(f"\r  {name}  (bitta bo'lak: {median:.0f} ms){' ' * 20}")
        print(f"    {'':<28}{'javob':>7}{'to`g`ri':>10}{'ishonchlilik':>15}")
        for row, _ in ROWS:
            answered, right = stats[row, "javob"], stats[row, "to'g'ri"]
            reliability = f"{right / answered:.0%}" if answered else "—"
            print(f"    {row:<28}{answered:>7}{right:>6} /{n:<3}{reliability:>12}")
        print()


if __name__ == "__main__":
    main()
