"""B5.3b-2: OCR'larni kesilgan bo'laklarda solishtirish — sana va raqam json bilan.

Har OCR uchun (make_crops yasagan bo'laklar, faqat dev):
- date.png   -> sana;  number.png -> raqam;  line.png -> sana va raqam (to'liq qator);
- header.png -> sana ("№" topilmagan xatlarda ham bor): birinchi sana, "от" dan keyingisi emas;
- "yangi qoida" — hozirgi tizim (matn qatlamidan sana avtomatik) + bo'sh qolgan joyga bo'lak OCR'i.
Hisob 70 xatga nisbatan (bo'lagi yo'q xat — javob yo'q). Javob: OCR biror qiymat chiqardi;
to'g'ri: json bilan mos (bo'shliqsiz solishtiriladi). Vaqt — bitta bo'lakka (median).
O'qilgan matnlar outputs/ocr/<OCR>.json ga QO'SHILADI (keyingi tahlil uchun; Claude OCHMAYDI):
oldin o'qilgan boshqa bo'laklar saqlanib qoladi, shu safar o'qilgan bo'lak — yangisi bilan.
Raqam — fields/number_vote.read_number (VLM JSON'i "raqam" maydoni, ko'p qatorlida "№" qatori).
Matnlar har xatdan keyin yoziladi (Mac qulasa ham o'qilgani qoladi). --ids — faqat shu xatlar
(sinov uchun); --saved — OCR ishlatilmaydi, oldin saqlangan matnlar baholanadi (bir xil xatlarda
ikki OCR'ni solishtirish uchun, masalan 2B va 4B).
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
from src.fields.date_number import OCR_PATTERNS, all_dates, date_and_number, parse_date
from src.fields.number_vote import read_number
from src.reading.engines import READERS, make_reader

CROPS_DIR = Path("outputs/crops")
OUT_DIR = Path("outputs/ocr")
ROWS = [  # (qator nomi, maydon)
    ("sana: date bo'lagi", "sana"),
    ("sana: line bo'lagi", "sana"),
    ("sana: yangi qoida", "sana"),
    ("sana: header bo'lagi", "sana"),
    ("sana: yangi qoida + header", "sana"),
    ("sana: page (butun sahifa)", "sana"),
    ("raqam: number bo'lagi", "raqam"),
    ("raqam: line bo'lagi", "raqam"),
    ("raqam: header bo'lagi", "raqam"),
    ("raqam: page (butun sahifa)", "raqam"),
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
        "sana: page (butun sahifa)": parse_date(
            texts.get("page", ""), skip_after_ot=True, patterns=OCR_PATTERNS
        ),
        "raqam: number bo'lagi": read_number("number", texts.get("number", "")),
        "raqam: header bo'lagi": read_number("header", texts.get("header", "")),
        "raqam: page (butun sahifa)": read_number("page", texts.get("page", "")),
        "raqam: line bo'lagi": read_number("line", texts.get("line", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readers", nargs="+", choices=sorted(READERS))
    parser.add_argument(
        "--crops",
        nargs="+",
        default=["date", "number", "line", "header"],
        help="o'qiladigan bo'laklar",
    )
    parser.add_argument("--ids", nargs="+", help="faqat shu xatlar (DOC_…)")
    parser.add_argument("--saved", action="store_true", help="OCR'siz — saqlangan matnlardan")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    if args.ids:
        dev = [d for d in dev if d in set(args.ids)]
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
        out = OUT_DIR / f"{name}.json"
        saved = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        reader = None if args.saved else make_reader(name)
        if hasattr(reader, "available") and not reader.available():
            print(f"  {name}: VLM serveri javob bermadi — avval alohida terminalda:")
            print("    sh scripts/ocr/vlm_server.sh\n")
            continue
        stats, times = Counter(), []
        for number, doc_id in enumerate(dev, 1):
            print(f"\r  {name}: {number}/{n} xat o'qilyapti…", end="", flush=True)
            if reader is None:  # --saved: faqat oldin o'qilgan bo'laklar
                old = saved.get(doc_id, {})
                texts = {crop: old[crop] for crop in args.crops if crop in old}
            else:
                texts = {}
                for crop in args.crops:
                    path = CROPS_DIR / doc_id / f"{crop}.png"
                    if path.exists():
                        start = time.perf_counter()
                        texts[crop] = reader.read(path.read_bytes())
                        times.append(time.perf_counter() - start)
                saved.setdefault(doc_id, {}).update(texts)
                out.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
            for row, value in answers(texts, text_layer_dates[doc_id]).items():
                if value:
                    stats[row, "javob"] += 1
                    stats[row, "to'g'ri"] += same(value, expected[doc_id][dict(ROWS)[row]])

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
