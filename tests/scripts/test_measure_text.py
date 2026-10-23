"""scripts/text/measure_text.py dagi qidiruv yordamchilari testlari — to'qilgan qiymatlar bilan."""

from scripts.text.measure_text import anchor_y, date_found, number_found
from src.reading.pdf_text import read_text_layer


def test_date_found_in_different_formats():
    assert date_found("05.12.2025", "Исх. 05.12.2025 № 1")
    assert date_found("05.12.2025", "5.12.25")
    assert date_found("05.12.2025", "05 / 12 / 2025")
    assert date_found("05.12.2025", "от 5 декабря 2025 г.")
    assert date_found("05.12.2025", "05 ДЕК 2025")  # shtamp ko'rinishi


def test_date_not_confused_with_other_dates():
    assert not date_found("05.12.2025", "15.12.2025")  # boshqa kun
    assert not date_found("05.12.2025", "05.11.2025")  # boshqa oy
    assert not date_found("05.12.2025", "05 ДЕК 2024")  # boshqa yil
    assert not date_found("noto'g'ri", "05.12.2025")


def test_number_found_exact_and_fuzzy():
    text = "Исх. № 12/34 - 56789 от ..."
    assert number_found("12/34-56789", text)  # bo'shliqlar hisobga olinmaydi
    assert not number_found("12/34-56788", text)
    assert number_found("12/34-56788", text, fuzzy=True)  # 1 belgi farq — "deyarli"
    assert not number_found("", text)


def test_anchor_y_finds_number_sign_on_first_page(letter_pdf):
    y = anchor_y(read_text_layer(letter_pdf))
    assert y is not None and 0.1 < y < 0.15  # soxta xatda "№" 110/842 punktda
