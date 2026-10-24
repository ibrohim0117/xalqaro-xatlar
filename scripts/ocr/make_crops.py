"""B5.3b-1: qo'lyozma joylarini rasm bo'lak qilib kesish — OCR modellari bir xil bo'laklarda
solishtiriladi.

Har dev xatning 1-sahifasidan (joylar keshdagi matndan, rasm PDF'dan, 300 dpi):
- line.png   — "sana № raqam" qatori; date.png — "№" dan chapi; number.png — o'ngi;
- reply.png  — "На № … от …" qatori (bo'lsa) — javob xatning mazmuni uchun;
- header.png — chap yuqori qism (langar topilmasa ham bor — VLM o'zi qidiradi).
outputs/crops/<DOC_id>/ ga yoziladi (gitignore).
MAXFIYLIK: bu real xat bo'laklari — Claude OCHMAYDI.
outputs/crops/manifest.json — qaysi bo'laklar bor va langar qayerdan topilgan (qiymatlar yo'q).
Ekranga faqat sonlar chiqadi.

Ishga tushirish: poetry run python -m scripts.ocr.make_crops
"""

import json
import time
from collections import Counter
from pathlib import Path

import pymupdf

from src.engine.locate import ocr_regions
from src.evaluation.dataset import list_letters, load_split
from src.evaluation.text_cache import get_pages
from src.fields.date_number import find_anchor
from src.reading.crops import crop_png, dpi_for
from src.reading.pages import CachedPage

OUT_DIR = Path("outputs/crops")


def anchor_source(first: CachedPage) -> str:
    if find_anchor(first.text_layer.words) is not None:
        return "matn qatlami"
    if first.ocr is not None and find_anchor(first.ocr.words) is not None:
        return "OCR"
    return "yo'q"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    manifest, anchors, crops = {}, Counter(), Counter()
    start = time.perf_counter()
    for doc_id in dev:
        letter = letters[doc_id]
        first = get_pages(letter)[0]
        folder = OUT_DIR / doc_id
        folder.mkdir(parents=True, exist_ok=True)
        found = ocr_regions(first)
        with pymupdf.open(letter.pdf) as doc:
            for name, place in found.items():
                (folder / f"{name}.png").write_bytes(crop_png(doc[0], place, dpi=dpi_for(name)))
        source = anchor_source(first)
        manifest[doc_id] = {"bo'laklar": sorted(found), "langar": source}
        anchors[source] += 1
        crops.update(found.keys())  # bo'lak nomlarini sanash (joylar lug'ati emas)
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))

    size = sum(f.stat().st_size for f in OUT_DIR.rglob("*.png")) / 1e6
    seconds = time.perf_counter() - start
    print(f"B5.3b-1: {len(dev)} dev xat, {seconds:.0f} s, {size:.0f} MB -> {OUT_DIR}/")
    print(
        "  '№' langari: " + ", ".join(f"{k} {anchors[k]}" for k in ("matn qatlami", "OCR", "yo'q"))
    )
    print(
        "  Bo'laklar:   "
        + ", ".join(
            f"{k} {crops[k]}" for k in ("line", "date", "number", "reply", "header", "page")
        )
    )


if __name__ == "__main__":
    main()
