"""B3.4: xatlar matnini bir marta olib keshga yozadi. Ekranga FAQAT raqamlar chiqadi.

Standart holatda faqat DEV xatlar: B4–B5 da test xatlari matni tasodifan ham o'qilmasligi uchun.
Test xatlari faqat B6 (yakuniy o'lchov) da --part test bilan keshlanadi.
Qayta ishga tushirilsa, keshda borlari o'tkazib yuboriladi (bir zumda).

Ishga tushirish:
    poetry run python -m scripts.build_cache              # 70 dev xat (birinchi marta ~5-6 daqiqa)
    poetry run python -m scripts.build_cache --limit 3    # tez sinov
    poetry run python -m scripts.build_cache --part test  # faqat B6 da!
"""

import argparse
import sys
import time
from collections import Counter

from src.dataset import list_letters, load_split
from src.text_cache import CACHE_DIR, get_pages, load


def main() -> None:
    parser = argparse.ArgumentParser(description="Xatlar matnini keshga yozish")
    parser.add_argument("--part", choices=["dev", "test"], default="dev", help="qaysi to'plam")
    parser.add_argument("--limit", type=int, default=None, help="faqat dastlabki N xat (sinov)")
    args = parser.parse_args()

    if args.part == "test":
        print("⚠️  TEST xatlari — faqat B6 (yakuniy o'lchov) uchun.\n")
    ids = set(load_split()[args.part])
    letters = [letter for letter in list_letters() if letter.doc_id in ids][: args.limit]
    already = sum(load(CACHE_DIR / f"{letter.doc_id}.json") is not None for letter in letters)
    started = time.perf_counter()
    pages, ocr_pages, main_source = 0, 0, Counter()
    for n, letter in enumerate(letters, 1):
        print(f"\r  {n}/{len(letters)}", end="", file=sys.stderr, flush=True)
        result = get_pages(letter)
        pages += len(result)
        ocr_pages += sum(page.ocr is not None for page in result)
        main_source.update(page.main.source for page in result)
    print(file=sys.stderr)
    elapsed = time.perf_counter() - started

    size_mb = sum(f.stat().st_size for f in CACHE_DIR.glob("*.json")) / 1e6
    print(f"Kesh: {CACHE_DIR}/ (gitga kirmaydi, faqat o'zingiz uchun)")
    new = len(letters) - already
    print(f"  {args.part} xatlar: {len(letters)} ({new} yangi, {already} oldin bor edi)")
    print(f"  sahifalar: {pages}, ulardan OCR qilingan: {ocr_pages}")
    print(
        f"  asosiy matn manbasi: matn qatlami {main_source['text_layer']},"
        f" OCR {main_source['ocr']} sahifa"
    )
    print(f"  vaqt: {elapsed / 60:.1f} daqiqa | hajm: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
