"""src/fields/date_number.py testlari — to'qilgan sana va raqamlar bilan."""

import pytest

from src.fields.date_number import (
    OCR_PATTERNS,
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("« 17 » 12 20 25 ý.", "17.12.2025"),  # Turkmaniston blanki
        ("«17» 12 2025 ý.", "17.12.2025"),
        ("19 12.25 nr. 02-1793", "19.12.2025"),  # Moldova: kun va oy orasida bo'shliq
        ("on the(date) 23.Oct.2025", "23.10.2025"),  # inglizcha oy, nuqtalar bilan
        ("от 12.11 20 25 г. № 1495", "12.11.2025"),  # yil ikkiga bo'lingan
        ("05.12.2025 № 54/07", "05.12.2025"),  # oddiy shakl ham ishlaydi
    ],
)
def test_ocr_date_shapes(text, expected):
    assert parse_date(text, patterns=OCR_PATTERNS) == expected


@pytest.mark.parametrize(
    "text",
    ["« 17 » 12 20 25 ý.", "19 12.25 nr. 02-1793", "on the(date) 23.Oct.2025"],
)
def test_text_layer_rule_is_unchanged(text):
    assert parse_date(text) is None  # avtomatik (matn qatlami) qoidasi yangi shakllarni olmaydi


@pytest.mark.parametrize(
    "text",
    [
        "tel. +373 22 26 72 93, fax: +373 29 26 92",  # telefon — sana emas
        "Telefon: (+993 12) 39-19-21; Faks: (+993 12) 39-19-71",
        "md-2012, str. Aleksandr Pushkin, nr.42",
    ],
)
def test_ocr_shapes_do_not_read_phones_as_dates(text):
    assert parse_date(text, patterns=OCR_PATTERNS) is None


def test_anchor_skips_bank_details_and_reply_lines():
    def line(tokens, y, n):
        x = [0.05 + 0.1 * k for k in range(len(tokens))]
        return [Word(t, x0, y, x0 + 0.09, y + 0.01, n) for t, x0 in zip(tokens, x, strict=True)]

    bank = line(["б/с", "№", "4402041101034673"], 0.20, 0)  # bank rekviziti — langar emas
    account = line(["№", "40702810900000012345"], 0.22, 1)  # 10+ raqamli hisob — langar emas
    reply = line(["На", "ваш", "исх.", "№", "20/21-5/5036"], 0.25, 2)  # bizning raqamimiz
    own = line(["17.01.2026", "№", "478"], 0.30, 3)  # xatning o'z sana-raqam qatori
    page = PageText(1, "text_layer", bank + account + reply + own)
    assert date_and_number(page) == ("17.01.2026", "478")
    assert date_and_number(PageText(1, "text_layer", bank + account + reply)) == (None, None)


def test_date_is_not_taken_from_inside_the_number():
    words = [
        Word("№03-01-26/785", 0.30, 0.25, 0.45, 0.26, 0),  # yopishgan raqam: ichida "03-01-26"
        Word("12.01.2026", 0.05, 0.25, 0.20, 0.26, 0),
    ]
    assert date_and_number(PageText(1, "text_layer", words)) == ("12.01.2026", "03-01-26/785")
    only_number = PageText(1, "text_layer", words[:1])
    assert date_and_number(only_number) == (None, "03-01-26/785")  # raqam ichidan sana olinmaydi


def test_date_of_the_recipient_block_is_not_the_letter_date():
    words = [  # matn qatlami so'zlarni aralash bergan: "от" o'ng blokda sanadan oldin emas
        Word("№", 0.20, 0.36, 0.22, 0.37, 0),
        Word("78/05-1/25", 0.23, 0.36, 0.35, 0.37, 0),
        Word("(№", 0.60, 0.36, 0.62, 0.37, 0),
        Word("от", 0.63, 0.36, 0.65, 0.37, 0),
        Word("10/04-2/25", 0.66, 0.36, 0.75, 0.37, 0),
        Word("03.12.2025)", 0.76, 0.36, 0.85, 0.37, 0),
    ]
    assert date_and_number(PageText(1, "text_layer", words)) == (None, "78/05-1/25")


def test_date_pattern_inside_a_number_is_not_a_date():
    assert parse_date("12.01 №03-01-26/785") is None  # OCR qatori: raqam ichida "03-01-26"
    assert parse_date("№03-01-26 от") is None  # "№" ga yopishgan — raqam
    assert parse_date("вих. № 12.01.2026") == "12.01.2026"  # bo'shliq bilan — sana bo'lishi mumkin
    assert parse_date("12.01.2026 № 55/07-1234") == "12.01.2026"
    assert parse_date("12.01.2026г. №03-01-26/785") == "12.01.2026"
    assert parse_date("№ 78/05-1/25") is None  # "05-1/25" — raqam o'rtasi ("78/" dan keyin)
