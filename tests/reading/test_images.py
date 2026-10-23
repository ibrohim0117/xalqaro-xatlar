"""src/reading/images.py testlari."""

import base64

from src.reading.images import page_images


def test_pages_become_jpeg_data_uris(letter_pdf):
    images = page_images(letter_pdf.read_bytes(), max_pages=6)
    assert len(images) == 2  # soxta xatda 2 sahifa — 6 dan kam bo'lsa, borlari
    head, data = images[0].split(",", 1)
    assert head == "data:image/jpeg;base64"
    assert base64.b64decode(data)[:2] == b"\xff\xd8"  # JPEG boshi
    assert len(page_images(letter_pdf.read_bytes(), max_pages=1)) == 1
