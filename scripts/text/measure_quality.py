"""B3.5: matn qatlami sifati — qancha sahifada u axlat? Ekranga FAQAT raqamlar chiqadi.

Sifat = harfli so'zlarning "toza" ulushi (src.reading.pdf_text.text_quality). Matn keshdan olinadi.
Ishga tushirish: poetry run python -m scripts.text.measure_quality
"""

from collections import Counter

from src.evaluation.dataset import list_letters, load_split
from src.evaluation.text_cache import get_pages
from src.reading.pdf_text import has_text_layer, text_quality

BINS = [(0.0, 0.4), (0.4, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
THRESHOLDS = [0.5, 0.6, 0.7, 0.8]


def bin_of(score: float) -> tuple[float, float]:
    return next(b for b in BINS if b[0] <= score < b[1])


def cleaner(text_layer_words, ocr_words) -> str:
    """Qaysi manba tozaroq (0.02 dan kichik farq — teng)."""
    diff = text_quality(ocr_words) - text_quality(text_layer_words)
    if diff > 0.02:
        return "OCR tozaroq"
    if diff < -0.02:
        return "matn qatlami tozaroq"
    return "deyarli teng"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    tl_bins, ocr_bins = Counter(), Counter()
    tl_scores: list[tuple[str, float]] = []
    first_page = Counter()  # 1-sahifada: matn qatlami va OCR qaysi biri tozaroq
    for doc_id in load_split()["dev"]:
        for page in get_pages(letters[doc_id]):
            tl_ok = has_text_layer(page.text_layer.words)
            if tl_ok:
                score = text_quality(page.text_layer.words)
                tl_bins[bin_of(score)] += 1
                tl_scores.append((doc_id, score))
            if page.ocr is not None:
                ocr_bins[bin_of(text_quality(page.ocr.words))] += 1
            if page.number == 1 and tl_ok and page.ocr is not None:
                first_page[cleaner(page.text_layer.words, page.ocr.words)] += 1

    print("B3.5: matn sifati (toza so'zlar ulushi), dev 70 xat\n")
    print(f"  {'sifat':<12}{'matn qatlami':>14}{'OCR':>8}   (sahifalar soni)")
    for low, high in BINS:
        label = f"{low:.1f}–{min(high, 1.0):.1f}"
        print(f"  {label:<12}{tl_bins[(low, high)]:>14}{ocr_bins[(low, high)]:>8}")

    print("\n  Chegara tanlansa — qayta OCR qilinadigan matn qatlami sahifalari:")
    for t in THRESHOLDS:
        pages = sum(score < t for _, score in tl_scores)
        docs = len({doc for doc, score in tl_scores if score < t})
        print(f"    sifat < {t:.1f}: {pages:>3} sahifa, {docs:>2} xatda")
    print(f"\n  1-sahifa (ikkala manba bor): {dict(first_page)}")


if __name__ == "__main__":
    main()
