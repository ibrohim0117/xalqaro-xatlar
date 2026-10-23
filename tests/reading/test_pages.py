"""src/reading/pages.py testlari — soxta xatlar bilan."""

from src.reading.pages import extract_pages
from src.reading.pdf_text import text_quality
from tests.conftest import make_garbage_layer_pdf, needs_tesseract, needs_uzb


@needs_tesseract
def test_extract_ocrs_first_page_and_pages_without_text_layer(letter_pdf):
    first, second = extract_pages(letter_pdf)
    assert first.ocr is not None  # 1-sahifa matn qatlami bo'lsa ham OCR qilinadi
    assert first.main.source == "text_layer"  # lekin asosiy matn — matn qatlami
    assert second.ocr is not None  # 2-sahifada 50 belgidan kam — matn qatlami yo'q deb olinadi
    assert second.main.source == "ocr"


@needs_tesseract
def test_extract_scanned_pdf_uses_ocr_everywhere(scanned_pdf):
    assert [page.main.source for page in extract_pages(scanned_pdf)] == ["ocr", "ocr"]


@needs_tesseract
def test_extract_from_bytes_and_only_first_pages(letter_pdf):
    from_bytes = extract_pages(letter_pdf.read_bytes(), max_pages=1)  # API: PDF xotiradan
    assert len(from_bytes) == 1  # 2-sahifa (ilova) o'qilmadi
    assert from_bytes[0].main.text == extract_pages(letter_pdf)[0].main.text


@needs_uzb
def test_garbage_text_layer_is_reread_with_uzbek(tmp_path):
    (page,) = extract_pages(make_garbage_layer_pdf(tmp_path / "guvohnoma.pdf"))
    assert text_quality(page.text_layer.words) < 0.5  # axlat matn qatlami
    assert page.main.source == "ocr"  # qayta o'qilgan matn tanlandi
    assert "Toshkent" in page.main.text and "Yunusobod" in page.main.text
