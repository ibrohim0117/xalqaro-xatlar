"""Bitta xatning PDF'dan olingan matnini FAYLGA yozadi — faqat Ibrohim o'zi ko'rishi uchun.

MAXFIYLIK: matn ekranga chiqmaydi, outputs/matn/ ga yoziladi (gitignore'da).
Bu faylni chatga nusxalamang — Claude real xatlarni ko'rmasligi kerak.

Ishga tushirish:
    poetry run python -m scripts.show_text DOC_1234567             # data/real dagi xat
    poetry run python -m scripts.show_text DOC_1234567 --pages 2   # faqat dastlabki 2 sahifa
    poetry run python -m scripts.show_text DOC_1234567 --ocr       # matn qatlami bo'lsa ham OCR
    poetry run python -m scripts.show_text outputs/soxta_xat.pdf   # istalgan PDF (masalan soxta)

TEST xatlari B6 (yakuniy o'lchov) gacha ko'rilmaydi — skript ularni rad etadi.
B6 dan keyin xatolarni tahlil qilish uchun: --test bayrog'i bilan.
"""

import argparse
import statistics
import time
from collections import Counter
from pathlib import Path

from src.dataset import list_letters, load_split
from src.pdf_text import PageText, read_ocr, read_pdf

OUT_DIR = Path("outputs/matn")


def render(pages: list[PageText]) -> str:
    parts = []
    for page in pages:
        header = f"===== {page.number}-sahifa | manba: {page.source} | {len(page.words)} so'z"
        if page.source == "ocr" and page.words:
            header += f" | o'rtacha ishonch {statistics.mean(w.conf for w in page.words):.0f}"
        parts.append(f"{header} =====\n{page.text or '(so`z topilmadi)'}")
    return "\n\n".join(parts) + "\n"


def find_pdf(target: str) -> Path | None:
    """DOC id bo'lsa — data/real dan, .pdf bo'lsa — shu faylning o'zi."""
    if target.lower().endswith(".pdf"):
        return Path(target) if Path(target).exists() else None
    return next((x.pdf for x in list_letters() if x.doc_id == target), None)


def is_test_letter(target: str) -> bool:
    """DOC id yoki data/real/DOC_.../fayl.pdf yo'li test to'plamiga tegishlimi."""
    doc_id = Path(target).parent.name if target.lower().endswith(".pdf") else target
    return doc_id in load_split()["test"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Xat matnini faylga yozish (faqat o'zingiz uchun)")
    parser.add_argument("target", help="DOC id (papka nomi) yoki .pdf fayl yo'li")
    parser.add_argument("--pages", type=int, default=None, help="nechta sahifa (standart: hammasi)")
    parser.add_argument("--ocr", action="store_true", help="matn qatlami bo'lsa ham OCR qilish")
    parser.add_argument(
        "--test", action="store_true", help="test xatini ko'rish (faqat B6 dan keyin)"
    )
    args = parser.parse_args()

    if is_test_letter(args.target) and not args.test:
        print("⚠️  Bu TEST xati. B6 (yakuniy o'lchov) gacha test xatlari ko'rilmaydi.")
        print("    B6 dan keyin xatolarni tahlil qilish uchun: --test bayrog'i bilan.")
        return

    pdf = find_pdf(args.target)
    if pdf is None:
        print(f"Topilmadi: {args.target}")
        return
    started = time.perf_counter()
    pages = read_ocr(pdf, args.pages) if args.ocr else read_pdf(pdf, args.pages)
    elapsed = time.perf_counter() - started

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{Path(args.target).stem}{'_ocr' if args.ocr else ''}.txt"
    out.write_text(render(pages), encoding="utf-8")
    sources = Counter(page.source for page in pages)
    print(f"Yozildi: {out}")
    print(
        f"  {len(pages)} sahifa: matn qatlami {sources['text_layer']}, OCR {sources['ocr']}"
        f" | {elapsed:.1f} s"
    )
    print("  Faylni o'zingiz oching. Matnni chatga nusxalamang.")


if __name__ == "__main__":
    main()
