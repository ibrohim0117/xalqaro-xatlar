"""src/reading/crops.py testlari."""

import pymupdf

from src.reading.crops import crop_png


def test_crop_has_the_requested_size(letter_pdf):
    with pymupdf.open(letter_pdf) as doc:
        png = crop_png(doc[0], {"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.2}, dpi=300, pad=0.0)
    pixmap = pymupdf.Pixmap(png)
    assert png[:4] == b"\x89PNG"
    assert abs(pixmap.width - 0.4 * 595 / 72 * 300) <= 2  # 0.4 sahifa kengligi, 300 dpi
    assert abs(pixmap.height - 0.1 * 842 / 72 * 300) <= 2


def test_padding_is_clipped_at_page_edge(letter_pdf):
    with pymupdf.open(letter_pdf) as doc:
        png = crop_png(doc[0], {"x0": 0.0, "y0": 0.0, "x1": 0.2, "y1": 0.1}, dpi=72, pad=0.05)
    assert abs(pymupdf.Pixmap(png).width - 0.25 * 595) <= 2  # chapga chiqmaydi, faqat o'ngga
