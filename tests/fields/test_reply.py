"""src/fields/reply.py testlari — to'qilgan qatorlar bilan."""

import pytest

from src.fields.reply import reply_of, reply_reference, reply_summary
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word


def page_of(*lines: str) -> PageText:
    """Har qator — alohida y (0.10, 0.12, …), so'zlar chapdan o'ngga."""
    words = []
    for k, line in enumerate(lines):
        for j, text in enumerate(line.split()):
            words.append(
                Word(text, 0.05 + 0.08 * j, 0.10 + 0.02 * k, 0.12 + 0.08 * j, 0.11 + 0.02 * k, k)
            )
    return PageText(1, "text_layer", words)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("На № 17/08-10/2934 от 05.12.2025", ("17/08-10/2934", "05.12.2025")),
        ("На Ваш исх. № 3-3-28/16847 от 30.09.2025", ("3-3-28/16847", "30.09.2025")),
        ("На№17/08-10/2934 от 05.12.2025", ("17/08-10/2934", "05.12.2025")),  # bo'shliqsiz
        ("На № ___ от ___", (None, None)),  # bo'sh qator
        ("На № 52/05- от ___", (None, None)),  # bosma boshi, davomi qo'lda — chala raqam olinmaydi
    ],
)
def test_reply_line(line, expected):
    page = page_of("ГЛАВНОЕ УПРАВЛЕНИЕ", "12.03.2026 № 55/07-1234", line)
    assert reply_reference(page) == expected


def test_own_number_line_is_not_a_reply():
    assert reply_reference(page_of("УПРАВЛЕНИЕ ЮСТИЦИИ", "12.03.2026 № 55/07-1234")) is None


def test_na_on_previous_line_does_not_count():
    # "на" oldingi qatorning oxirida — "№" esa yangi qatorda (xatning o'z raqami)
    assert reply_reference(page_of("Просим ответить на", "№ 55/07-1234 от 12.03.2026")) is None


def test_ocr_is_used_when_text_layer_line_is_empty():
    empty = page_of("На № ___ от ___")
    filled = page_of("На № 17/08-10/2934 от 05.12.2025")
    assert reply_of(CachedPage(1, empty, filled)) == ("17/08-10/2934", "05.12.2025")
    assert reply_of(CachedPage(1, empty, None)) == (None, None)


def test_summary_template():
    assert (
        reply_summary("17/08-10/2934", "05.12.2025")
        == "05.12.2025-yildagi 17/08-10/2934-son xat ijrosi bo'yicha"
    )
