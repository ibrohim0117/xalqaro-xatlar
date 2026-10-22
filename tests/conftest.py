"""Testlar uchun umumiy narsalar: soxta (to'qilgan) xat PDF'i.

Xatdagi hamma nom, raqam va shaxslar to'qilgan. Joylashuv real xatlar tuzilishiga o'xshatilgan:
chapda jo'natuvchi va "sana № raqam", o'ngda qabul qiluvchi, pastda imzo.
"""

from pathlib import Path

import pymupdf
import pytest

# (x, y punktlarda, matn). A4 = 595 x 842 punkt, y yuqoridan pastga o'sadi.
FAKE_LETTER = [
    (50, 60, "УПРАВЛЕНИЕ ЮСТИЦИИ"),
    (50, 76, "ВЫМЫШЛЕННОЙ ОБЛАСТИ"),
    (50, 110, "12.03.2026 № 55/07-1234"),
    (340, 60, "Министерство юстиции"),
    (340, 76, "Республики Узбекистан"),
    (340, 92, "г. Ташкент"),
    (50, 200, "Просим вручить документы гражданину,"),
    (50, 216, "проживающему: Узбекистан, Ферганская область."),
    (50, 700, "Начальник управления"),
    (400, 700, "А.Б. Сидоров"),
]
FAKE_APPENDIX = [(50, 60, "Приложение на 2 листах")]


def make_letter_pdf(path: Path) -> Path:
    """2 sahifali soxta xat: 1-sahifa — xatning o'zi, 2-sahifa — ilova."""
    font = pymupdf.Font("cjk").buffer  # PyMuPDF ichidagi shrift, kirill harflari bor
    doc = pymupdf.open()
    for lines in (FAKE_LETTER, FAKE_APPENDIX):
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname="F0", fontbuffer=font)
        for x, y, text in lines:
            page.insert_text((x, y), text, fontname="F0", fontsize=12)
    doc.save(path)
    return path


def make_scanned_pdf(path: Path, source: Path, dpi: int = 200) -> Path:
    """Skaner xatni taqlid qiladi: har sahifa rasmga aylantirilib, matnsiz PDF'ga joylanadi."""
    doc = pymupdf.open()
    with pymupdf.open(source) as src:
        for page in src:
            new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=page.get_pixmap(dpi=dpi))
    doc.save(path)
    return path


@pytest.fixture
def letter_pdf(tmp_path: Path) -> Path:
    return make_letter_pdf(tmp_path / "soxta_xat.pdf")


@pytest.fixture
def scanned_pdf(tmp_path: Path, letter_pdf: Path) -> Path:
    return make_scanned_pdf(tmp_path / "soxta_skaner.pdf", letter_pdf)
