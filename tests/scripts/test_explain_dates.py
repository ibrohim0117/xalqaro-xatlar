"""scripts/ocr/explain_dates.py testlari — to'qilgan matnlar bilan."""

import pytest

from scripts.ocr.explain_dates import relation

TRUTH = "16.12.2025"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("16.12.2025 № 25/05", "to'g'ri"),
        ("16.12.2015 № 25/05", "yil farq"),  # qo'lyozma raqam xato o'qilgan
        ("18.12.2025", "kun farq"),
        ("16.10.2025", "oy farq"),
        ("На № 20/21 от 16.10.2025", "faqat 'от' dan keyingi boshqa sana"),  # boshqa qatordagi sana
        ("16.12.2025\nНа № 20/21 от 16.10.2025", "to'g'ri (+1 boshqa sana)"),
        ("01.02.2024", "butunlay boshqa sana"),
        ("№ 25/05", "sana o'qilmadi"),
    ],
)
def test_relation_without_values(text, expected):
    assert relation(text, TRUTH) == expected
