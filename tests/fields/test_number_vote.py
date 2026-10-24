"""src/fields/number_vote.py testlari — to'qilgan OCR matnlari bilan."""

import pytest

from src.fields.number_template import fit, learn
from src.fields.number_vote import (
    anchor_number,
    confirmed_number,
    engine_numbers,
    number_reading,
    ranked_numbers,
    read_number,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"sana": "12.03.2026", "raqam": "55/07-1234"}', "55/07-1234"),
        ('```json\n{"sana": "12.03.2026", "raqam": "№ 54/07 - 16606"}\n```', "54/07-16606"),
        ('{"sana": "12.03.2026", "raqam": null}', None),  # sana bor, raqam yo'q — sanani olmaydi
    ],
)
def test_vlm_json_number(text, expected):
    assert read_number("header", text) == expected


def test_multi_line_text_takes_only_the_number_line():
    header = "ул. Ленина 15, тел. 22-33-44\n12.03.2026 No 55/07-1234\nНа № 17/08 от 01.10.2025"
    assert anchor_number(header) == "55/07-1234"  # manzil, telefon va "На №" emas
    assert anchor_number("На № 17/08 от 01.10.2025") is None
    assert read_number("header", header) == "55/07-1234"
    assert read_number("line", "12.03.2026 № 55/07-1234") == "55/07-1234"  # bitta qator — butunicha


def test_engine_numbers_skip_the_date_crop():
    found = engine_numbers({"date": "12.03.2026", "number": "55/07-1234"})
    assert found == {"number": "55/07-1234"}


def test_vlm_number_needs_another_ocr():
    vlm = {"header": "55/07-1234"}
    assert confirmed_number([vlm, {"number": "55/07-1234"}]) == "55/07-1234"
    assert confirmed_number([vlm, {"line": "55/07 - 1234"}]) == "55/07-1234"  # bo'shliq — farq emas
    assert confirmed_number([vlm, {"number": "55/07-1284"}]) is None  # bitta raqam farq — tasdiqmas
    no_header = [{"line": "55/07-1234"}, {"number": "55/07-1234"}]
    assert confirmed_number(no_header) is None  # 1-OCR header'da raqam o'qimagan


def test_ranked_numbers_one_vote_per_ocr():
    found = [
        {"header": "55/07-1234", "line": "55/07-1234"},  # bitta OCR ikki bo'lakda — bitta ovoz
        {"number": "55/07-1284"},
        {"number": "55/07-1284"},
    ]
    assert ranked_numbers(found) == ["55/07-1284", "55/07-1234"]
    assert ranked_numbers([{}, {"line": None}]) == []


def test_number_reading_rule():
    template = learn(["54/07-17001/25", "54/07-9912/25"])
    header = {"header": "34/07-16606/25"}  # VLM bosh qismni xato o'qigan — qolip tuzatadi
    text = {"matn qatlami": None, "sahifa OCR": None}
    readers = ["vlm-extract", "vlm", "rapidocr"]
    old_vlm_only = [header, {"line": "54/07-16606/25"}, {}]
    prefill, suggestions = number_reading(readers, old_vlm_only, text, template)
    assert prefill is None  # faqat eski VLM tasdiqladi — hisob emas
    assert suggestions == ["54/07-16606/25"]  # ikkala o'qish qolip bilan bir xil bo'ldi
    confirmed = [header, {}, {"number": "54/07 16606/25"}]
    assert number_reading(readers, confirmed, text, template)[0] == "54/07-16606/25"
    # topuvchi (aniq savol) ishlamagan — yozilmaydi, faqat takliflar
    prefill, suggestions = number_reading(["rapidocr"], [{"number": "54/07-16606/25"}], text, None)
    assert prefill is None and suggestions == ["54/07-16606/25"]


def test_fit_is_idempotent():
    template = learn(["54/07-17001/25", "54/07-9912/25"])
    once = fit("34/07/16606/25", template)
    assert once == "54/07-16606/25" and fit(once, template) == once
