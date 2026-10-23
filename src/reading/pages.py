"""PDF'dan sahifalar matnini olish: matn qatlami va kerakli joyda OCR.

Qoidalar (B3.3 va B3.5 xulosalari):
- hamma sahifa: matn qatlami (bir zumda);
- 1-sahifa: OCR ham — "№" langarini OCR yaxshiroq topadi (80% ga qarshi 65%);
- matn qatlami yo'q sahifalar: OCR;
- eng yaxshi matn sifati 0.7 dan past sahifalar: rus+uzb bilan qayta OCR (lotin yozuvidagi
  FHDYO guvohnomalari va h.k.; dev'da matn qatlami sahifalarining 15% i 0.6 dan past).
"""

import time
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from src.reading.pdf_text import PageText, has_text_layer, ocr_page, text_layer_words, text_quality

QUALITY_MIN = 0.7  # eng yaxshi matn sifati shundan past bo'lsa — rus+uzb bilan qayta OCR
LATIN_LANG = "rus+uzb"  # o'zbek lotin yozuvini ham o'qiydi
MAIN_MARGIN = 0.02  # OCR shunchalik tozaroq bo'lsagina matn qatlami o'rniga olinadi
RETRY_MIN_WORDS = 10  # bo'sh yoki deyarli bo'sh sahifa qayta o'qilmaydi


@dataclass
class CachedPage:
    number: int
    text_layer: PageText
    ocr: PageText | None  # 1-sahifa, matn qatlami yo'q yoki sifati past sahifalar uchun

    @property
    def main(self) -> PageText:
        """Asosiy matn: matn qatlami va OCR'dan tozarog'i. Teng bo'lsa — matn qatlami."""
        if self.ocr is None:
            return self.text_layer
        if not has_text_layer(self.text_layer.words):
            return self.ocr
        if text_quality(self.ocr.words) > text_quality(self.text_layer.words) + MAIN_MARGIN:
            return self.ocr
        return self.text_layer


@dataclass
class OcrStats:
    """OCR hisoblagichi: necha marta chaqirildi va qancha vaqt ketdi (qayta OCR ham sanaladi)."""

    calls: int = 0
    seconds: float = 0.0


def _ocr(page: pymupdf.Page, number: int, stats: OcrStats | None, lang: str = "rus") -> PageText:
    start = time.perf_counter()
    result = ocr_page(page, number, lang=lang)
    if stats is not None:
        stats.calls += 1
        stats.seconds += time.perf_counter() - start
    return result


def extract_pages(
    pdf: Path | bytes, max_pages: int | None = None, stats: OcrStats | None = None
) -> list[CachedPage]:
    """PDF'dan sahifalarni o'qiydi: matn qatlami har doim, OCR faqat kerakli sahifalarda.
    pdf — fayl yo'li yoki baytlar (API: yuklangan PDF diskka yozilmaydi, xotiradan ochiladi).
    max_pages — faqat dastlabki N sahifa (None — hammasi, kesh uchun).
    stats — berilsa, OCR'ga ketgan vaqt shu yerga yig'iladi (API javobidagi "vaqt")."""
    pages = []
    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    with doc:
        for i, page in enumerate(doc):
            number = i + 1
            if max_pages is not None and number > max_pages:
                break
            words = text_layer_words(page)
            need_ocr = number == 1 or not has_text_layer(words)
            ocr = _ocr(page, number, stats) if need_ocr else None
            cached = CachedPage(number, PageText(number, "text_layer", words), ocr)
            main = cached.main
            if len(main.words) >= RETRY_MIN_WORDS and text_quality(main.words) < QUALITY_MIN:
                latin = _ocr(page, number, stats, lang=LATIN_LANG)
                if ocr is None or text_quality(latin.words) > text_quality(ocr.words):
                    cached.ocr = latin
            pages.append(cached)
    return pages
