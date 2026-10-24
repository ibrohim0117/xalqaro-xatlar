"""src/fields/reply.py testlari — to'qilgan qatorlar bilan."""

import pytest

from src.fields.number_template import shape
from src.fields.reply import (
    our_reference,
    own_numbers,
    parse_reply_summary,
    reply_of,
    reply_reference,
    reply_summary,
)
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


def body(text: str) -> list[CachedPage]:
    words = [Word(token, 0.1, 0.6, 0.2, 0.61, 0) for token in text.split()]
    return [CachedPage(2, PageText(2, "text_layer", words), None)]


OURS = {"99/99-99/9999"}  # boshqa javob xatlardan o'rganilgan shakl


def test_our_reference_by_shape_skips_decoys():
    text = (
        "12.03.2026 № 54/07-16606/25 По делу № 2-345/2025 на Ваш запрос № 77 от 01.02.2025 "
        "на письмо Министерства юстиции Республики Узбекистан от 05.06.2025 № 17/08-10/ 2934"
    )
    own = {"54/07-16606/25"}  # xatning o'z raqami
    assert our_reference(body(text), own, OURS) == ("17/08-10/2934", "05.06.2025")
    assert our_reference(body(text), own, {"99/99-99999/99"}) is None  # o'z raqami — chetlanadi


def test_our_number_needs_a_date_nearby():
    assert our_reference(body("Министерства юстиции № 17/08-10/2934 сообщаем"), set(), OURS) is None


def test_shape_hides_values():
    assert shape("17/08-10/2934") == "99/99-99/9999"


def test_date_right_after_glued_number_is_kept():
    text = "письмо Министерства юстиции №17/08-10/2934, от 05.06.2025 сообщаем"
    assert our_reference(body(text), set(), OURS) == ("17/08-10/2934", "05.06.2025")


def test_parse_reply_summary():
    summary = "05.06.2025-yildagi 17/08-1/2934-son xat ijrosi bo'yicha"
    assert parse_reply_summary(summary) == ("05.06.2025", "17/08-1/2934")
    assert parse_reply_summary("Xalqaro huquqiy yordam yuzasidan") is None
    assert parse_reply_summary(None) is None


def test_own_numbers_skip_the_bottom_half():
    first = body("12.03.2026 № 54/07-16606/25 Министерство юстиции")[0]  # y = 0.6
    assert own_numbers(first) == set()  # "№" langari faqat sahifaning yuqori yarmida
