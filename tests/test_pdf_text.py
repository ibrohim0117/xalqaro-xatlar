"""src/pdf_text.py testlari — faqat soxta xat bilan (tests/conftest.py)."""

import shutil

import pytest

from src.pdf_text import TESSDATA, PageText, read_ocr, read_pdf, read_text_layer

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None or not (TESSDATA / "rus.traineddata").exists(),
    reason="Tesseract yoki models/tessdata/rus.traineddata yo'q",
)


def find(page: PageText, text: str):
    return next(word for word in page.words if word.text == text)


def test_text_layer_reads_words_and_lines(letter_pdf):
    pages = read_text_layer(letter_pdf)
    assert [(p.number, p.source) for p in pages] == [(1, "text_layer"), (2, "text_layer")]
    assert "12.03.2026 № 55/07-1234" in pages[0].text.splitlines()
    assert pages[1].text == "Приложение на 2 листах"


def test_positions_are_relative_and_match_layout(letter_pdf):
    page = read_text_layer(letter_pdf)[0]
    for word in page.words:
        assert 0 <= word.x0 < word.x1 <= 1 and 0 <= word.y0 < word.y1 <= 1

    date = find(page, "12.03.2026")
    assert date.x0 < 0.5 and date.y0 < 0.2  # chap yuqorida
    tashkent = find(page, "Ташкент")
    assert tashkent.x0 > 0.5 and tashkent.y0 < 0.2  # o'ng yuqorida — qabul qiluvchi bloki
    signer = find(page, "Сидоров")
    assert signer.y0 > 0.7  # pastda


def test_max_pages(letter_pdf):
    assert len(read_text_layer(letter_pdf, max_pages=1)) == 1


def test_scanned_pdf_has_no_text_layer(scanned_pdf):
    assert all(not page.words for page in read_text_layer(scanned_pdf))


@needs_tesseract
def test_ocr_reads_scanned_letter_with_positions(scanned_pdf):
    page = read_ocr(scanned_pdf, max_pages=1)[0]
    assert page.source == "ocr"
    assert "12.03.2026" in page.text and "55/07-1234" in page.text
    assert all(word.conf is not None for word in page.words)

    tashkent = find(page, "Ташкент")
    assert tashkent.x0 > 0.5 and tashkent.y0 < 0.2  # o'ng yuqorida, B3.1 dagi bilan bir xil
    assert find(page, "Сидоров").y0 > 0.7


@needs_tesseract
def test_read_pdf_picks_source_per_page(letter_pdf, scanned_pdf):
    assert [p.source for p in read_pdf(letter_pdf)] == ["text_layer", "ocr"]  # 2-sahifa < 50 belgi
    assert [p.source for p in read_pdf(scanned_pdf)] == ["ocr", "ocr"]
