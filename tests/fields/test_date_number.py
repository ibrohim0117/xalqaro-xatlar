"""src/fields/date_number.py testlari — to'qilgan sana va raqamlar bilan."""

import pytest

from src.fields.date_number import (
    all_dates,
    date_and_number,
    is_date_token,
    parse_date,
    parse_number,
    plausible_number,
)
from src.reading.pdf_text import PageText, Word


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("05.12.2025", "05.12.2025"),
        ("5.12.25", "05.12.2025"),  # 2 xonali yil
        ("19 12.25", None),  # birinchi ajratuvchi yo'q — sana deb olinmaydi
        ("05 ДЕК 2025", "05.12.2025"),  # shtamp ko'rinishi
        ("«5» декабря 2025 г.", "05.12.2025"),
        ("2025 / 12 /22", "22.12.2025"),  # yil oldinda (Gruziya)
        ("32.13.2025", None),  # kun/oy noto'g'ri — OCR axlati
        ("№ 54/07-16606", None),  # raqam sana emas
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def page(items: list[tuple[str, float, float]]) -> PageText:
    """Soxta 1-sahifa: (so'z, x, y)."""
    return PageText(1, "ocr", [Word(t, x, y, x + 0.05, y + 0.01, 0) for t, x, y in items])


def test_typical_header_line():
    words = [("05.12.2025", 0.1, 0.30), ("№", 0.3, 0.30), ("54/07-16606", 0.33, 0.30)]
    assert date_and_number(page(words)) == ("05.12.2025", "54/07-16606")


@pytest.mark.parametrize("number", ["3-3-28/16847", "17/08-10/2934", "52/05-19719/25"])
def test_number_containing_a_date_like_part(number):
    # "3-3-28" sanaga o'xshaydi (03.03.2028), lekin so'z butunligicha — raqam
    words = [("30.09.26", 0.1, 0.30), ("№", 0.3, 0.30), (number, 0.33, 0.30)]
    assert date_and_number(page(words)) == ("30.09.2026", number)


def test_number_glued_to_sign_and_date_on_other_side():
    words = [("2025", 0.1, 0.35), ("/", 0.14, 0.35), ("12", 0.16, 0.35), ("/22", 0.19, 0.35),
             ("№01/301495", 0.8, 0.35)]  # fmt: skip
    assert date_and_number(page(words)) == ("22.12.2025", "01/301495")


def test_reply_line_is_a_trap():
    words = [
        ("На", 0.1, 0.40), ("№", 0.13, 0.40), ("12/345", 0.16, 0.40), ("от", 0.3, 0.40),
        ("01.11.2025", 0.33, 0.40),
    ]  # fmt: skip
    assert date_and_number(page(words)) == (None, None)  # faqat "На №" qatori — langar yo'q


def test_empty_number_field_is_not_guessed():
    words = [("05.12.2025", 0.1, 0.30), ("№", 0.3, 0.30), ("от", 0.5, 0.30)]
    assert date_and_number(page(words)) == ("05.12.2025", None)


def test_romanian_anchor():
    words = [("19.12.25", 0.1, 0.25), ("nr.", 0.3, 0.25), ("02-1793", 0.33, 0.25)]
    assert date_and_number(page(words)) == ("19.12.2025", "02-1793")


def test_printed_prefix_without_handwritten_rest_is_not_a_number():
    words = [("05.12.2025", 0.1, 0.30), ("№", 0.3, 0.30), ("52/05-", 0.33, 0.30)]
    assert date_and_number(page(words)) == ("05.12.2025", None)  # chala raqam yozilmaydi


def test_copy_recipient_date_after_ot_is_skipped():
    words = [
        ("№", 0.3, 0.30), ("52/05-", 0.33, 0.30),  # sana shtamp bilan — o'qilmagan
        ("на", 0.55, 0.30), ("№", 0.58, 0.30), ("03/01-48/3702", 0.6, 0.30), ("от", 0.75, 0.30),
        ("18.11.2025", 0.78, 0.30),  # nusxa oluvchining sanasi — tuzoq
    ]  # fmt: skip
    assert date_and_number(page(words)) == (None, None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("54/07-16606", True),
        ("01/301495", True),  # Gruziya
        ("21-02.02.03.03-14/123", True),  # nuqtali raqamlar ham bor (dev'da to'g'ri topilgan)
        ("123", True),  # qisqa raqamlar ham bor
        ("54/0Я", False),  # ichida kirill harfi — qo'lyozmadan OCR axlati
        ("Я-12345", False),
    ],
)
def test_plausible_number(value, expected):
    assert plausible_number(value) is expected


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("05.12.2025", True),
        ("17/08-10/2934", False),
        ("3-3-28/16847", False),
        ("54/07-16606", False),
    ],
)
def test_is_date_token(token, expected):
    assert is_date_token(token) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30.09.26 № 3-3-28/16847", "3-3-28/16847"),  # butun qator: sana o'tkazib yuboriladi
        ("№01/301495", "01/301495"),
        ("12.03.2026№55/07-1234", "55/07-1234"),  # OCR bo'shliqsiz bergan qator
        ("54/07-16606", "54/07-16606"),  # faqat raqam bo'lagi
        ("№ ___ от ___", None),
        ("52/05-", None),  # chala
        ("", None),
    ],
)
def test_parse_number_from_ocr_text(text, expected):
    assert parse_number(text) == expected


def test_all_dates_in_order_with_ot_mark():
    text = "05.12.2025 № 54/07 На № 17/08 от 01.10.2025. Справка от 3 мая 2024 г."
    assert all_dates(text) == [("05.12.2025", False), ("01.10.2025", True), ("03.05.2024", True)]
