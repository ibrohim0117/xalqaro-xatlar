"""B5.3b-2a: bo'laklar to'g'ri joydan kesilganmi — rasmlarni ochmasdan, faqat koordinatalar bilan.

Dev xatlarida:
1. sahifa burilganmi (rotation) yoki ko'rinadigan qismi (0, 0) dan boshlanmaydimi — koordinatalar
   siljishi mumkin;
2. "sana № raqam" qatoridan topilgan sana va raqam so'zlari date/number bo'lagi ichiga tushadimi;
3. line bo'lagi ichida nechta matn qatori bor (Tesseract --psm 7 bitta qator kutadi).
Ekranga FAQAT sonlar chiqadi.

Ishga tushirish: poetry run python -m scripts.ocr.check_crops
"""

import statistics
from collections import Counter

import pymupdf

from src.engine.locate import ocr_regions
from src.evaluation.dataset import list_letters, load_split
from src.evaluation.text_cache import get_pages
from src.fields.date_number import DATE_BAND, SAME_LINE, find_anchor, is_date_token, parse_number
from src.reading.crops import CROP_PAD
from src.reading.pdf_text import PageText, Word


def inside(word: Word, box: dict, pad: float = CROP_PAD) -> bool:
    """So'zning markazi bo'lak ichidami (kesishdagi zaxira bilan)."""
    cx, cy = (word.x0 + word.x1) / 2, (word.y0 + word.y1) / 2
    return box["x0"] - pad <= cx <= box["x1"] + pad and box["y0"] - pad <= cy <= box["y1"] + pad


def anchor_words(page: PageText) -> tuple[list[Word], list[Word]]:
    """("№" qatoridagi sana so'zlari, raqam so'zlari) — matn qaysi manbadan bo'lsa, o'shandan."""
    i = find_anchor(page.words)
    if i is None:
        return [], []
    a = page.words[i]
    band = [w for w in page.words if abs(w.y0 - a.y0) <= DATE_BAND]
    dates = [w for w in band if is_date_token(w.text.strip(".,г"))]
    numbers = [
        w
        for w in page.words
        if abs(w.y0 - a.y0) <= SAME_LINE and w.x0 > a.x0 and parse_number(w.text)
    ]
    return dates, numbers


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    pages, hits, lines_in_crop = Counter(), Counter(), []
    for doc_id in dev:
        letter = letters[doc_id]
        with pymupdf.open(letter.pdf) as doc:
            page = doc[0]
            pages["burilgan (rotation != 0)"] += page.rotation != 0
            pages["boshlanishi (0, 0) emas"] += tuple(page.rect[:2]) != (0, 0)
        first = get_pages(letter)[0]
        found = ocr_regions(first)
        if "line" not in found:
            continue
        for source, text in (("matn qatlami", first.text_layer), ("OCR", first.ocr)):
            if text is None:
                continue
            dates, numbers = anchor_words(text)
            for kind, words, crop in (("sana", dates, "date"), ("raqam", numbers, "number")):
                for word in words:
                    hits[source, kind, "jami"] += 1
                    hits[source, kind, "bo'lakda"] += inside(word, found[crop])
                    hits[source, kind, "line bo'lagida"] += inside(word, found["line"])
        main_words = first.main.words
        lines_in_crop.append(len({w.line for w in main_words if inside(w, found["line"])}))

    print(f"B5.3b-2a: bo'laklar joyi, dev {len(dev)} xat\n")
    for key in ("burilgan (rotation != 0)", "boshlanishi (0, 0) emas"):
        print(f"  1-sahifa {key:<28} {pages[key]:>3}")
    print("\n  '№' qatoridagi so'zlar bo'lak ichidami:  jami   o'z bo'lagida   line bo'lagida")
    for source in ("matn qatlami", "OCR"):
        for kind in ("sana", "raqam"):
            total = hits[source, kind, "jami"]
            own, line = hits[source, kind, "bo'lakda"], hits[source, kind, "line bo'lagida"]
            print(f"    {source:<13} {kind:<6} {total:>18} {own:>15} {line:>16}")
    if lines_in_crop:
        print(
            f"\n  line bo'lagidagi matn qatorlari: median {statistics.median(lines_in_crop)}, "
            f"eng ko'pi {max(lines_in_crop)}, 1 tadan ko'p: "
            f"{sum(n > 1 for n in lines_in_crop)}/{len(lines_in_crop)}"
        )


if __name__ == "__main__":
    main()
