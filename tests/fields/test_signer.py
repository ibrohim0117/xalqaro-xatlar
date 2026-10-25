"""src/fields/signer.py testlari — to'qilgan ismlar bilan."""

import pytest

from src.fields.signer import candidates, choose_signer, format_signer, parse_json_signer
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word


def test_parse_json_signer_shapes():
    assert parse_json_signer("O.N.Xrushev") == (["O", "N"], "Xrushev")
    assert parse_json_signer("M.Burkadze") == (["M"], "Burkadze")
    assert parse_json_signer("Sh.A.Rahimov") == (["Sh", "A"], "Rahimov")
    assert parse_json_signer("O. N. Xrushev") == (["O", "N"], "Xrushev")  # bo'shliqli
    assert parse_json_signer("Xrushev Oleg") is None  # boshqa shakl
    assert parse_json_signer(None) is None


def test_format_signer():
    assert format_signer(["O", "N"], "Xrushev") == "O.N.Xrushev"
    assert format_signer(["M"], "Burkadze") == "M.Burkadze"


def page(number: int, items: list[tuple[str, float, float, int]]) -> CachedPage:
    """Soxta sahifa: (so'z, x, y, qator)."""
    words = [Word(text, x, y, x + 0.05, y + 0.01, line) for text, x, y, line in items]
    return CachedPage(number, PageText(number, "text_layer", words), None)


LETTER_END = [
    ("Гражданину", 0.1, 0.3, 0),
    ("Иванову", 0.25, 0.3, 0),
    ("П.С.", 0.35, 0.3, 0),  # fuqaro: "Фамилия И.О." — nomzod emas
    ("Начальник", 0.1, 0.8, 1),  # boshqa qatorda: "П.С. Начальник" bo'lib qolmasligi kerak
    ("управления", 0.2, 0.8, 1),
    ("А.Б.", 0.7, 0.8, 1),
    ("Сидоров", 0.76, 0.8, 1),
]


def test_signer_found_at_letter_end():
    found = candidates([page(1, LETTER_END)])
    assert [(c.initials, c.surname) for c in found] == [(("А", "Б"), "Сидоров")]
    assert choose_signer(found).latin() == "A.B.Sidorov"


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        ([("А.", 0.6, 0.8, 0), ("Б.", 0.64, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)], "A.B.Sidorov"),
        ([("А.Б.", 0.6, 0.8, 0), ("СИДОРОВ", 0.7, 0.8, 0)], "A.B.Sidorov"),  # katta harflar
        # "Х" -> "X": dev'da o'girish 46 tadan 43 tasida aynan mos, "x→h" farqi uchramadi
        ([("Ш.Х.", 0.6, 0.8, 0), ("Шарипов", 0.7, 0.8, 0)], "Sh.X.Sharipov"),
        ([("М.", 0.6, 0.8, 0), ("Буркадзе", 0.7, 0.8, 0)], "M.Burkadze"),
        # B5.9: bosh harf "Е." -> "E." (so'z boshidagi "Ye" emas)
        ([("Е.П.", 0.6, 0.8, 0), ("Иванов", 0.7, 0.8, 0)], "E.P.Ivanov"),
        # B5.9: ukraincha harflar
        ([("І.В.", 0.6, 0.8, 0), ("Шевченко", 0.7, 0.8, 0)], "I.V.Shevchenko"),
        # B5.9: Ukraina imzosi "Имя ФАМИЛИЯ" — bitta bosh harf ismdan
        ([("Олена", 0.6, 0.8, 0), ("МЕЛЬНИЧУК", 0.7, 0.8, 0)], "O.Melnichuk"),
        # B5.9: bosh harf familiyaga yopishgan
        ([("А.Сидоров", 0.6, 0.8, 0)], "A.Sidorov"),
        ([("А.Б.Сидоров,", 0.6, 0.8, 0)], "A.B.Sidorov"),
        # B5.9: PDF matni "А.Б." ni ikkiga bo'lgan; oxirgi nuqta o'rnida vergul
        ([("А", 0.6, 0.8, 0), (".Б.", 0.62, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)], "A.B.Sidorov"),
        ([("А.Б,", 0.6, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)], "A.B.Sidorov"),
    ],
)
def test_signer_shapes(items, expected):
    assert choose_signer(candidates([page(1, items)])).latin() == expected


def test_choose_signer_prefers_right_half_and_last_page():
    left = page(1, [("А.Б.", 0.1, 0.9, 0), ("Сидоров", 0.15, 0.9, 0)])
    assert choose_signer(candidates([left])) is None  # chap yarmida — imzo emas
    assert choose_signer(candidates([left]), right_only=False).surname == "Сидоров"
    second = page(2, [("В.Г.", 0.6, 0.4, 0), ("Петров", 0.7, 0.4, 0)])
    assert choose_signer(candidates([page(1, LETTER_END), second])).surname == "Петров"


def test_recipient_person_in_header_is_not_signer():
    header = [("Заместителю", 0.6, 0.15, 0), ("В.Г.", 0.6, 0.18, 1), ("Иванову", 0.66, 0.18, 1)]
    found = candidates([page(1, header)])
    assert choose_signer(found).surname == "Иванову"  # filtrsiz — qabul qiluvchi imzo bo'lib qoladi
    assert choose_signer(found, min_y=0.5) is None  # pastki yarmi sharti bilan — "tekshirish kerak"


@pytest.mark.parametrize(
    "items",
    [
        [("Начальник", 0.6, 0.8, 0), ("ОТДЕЛА", 0.7, 0.8, 0)],  # lavozim — ism emas
        [("Олена", 0.6, 0.78, 0), ("МЕЛЬНИЧУК", 0.6, 0.8, 1)],  # ism boshqa qatorda
        [("Олена", 0.6, 0.8, 0), ("Мельничук", 0.7, 0.8, 0)],  # familiya katta harfda emas
        # gap ichida: katta harfli so'zdan keyin yana so'z bor — imzo emas
        [("Республики", 0.6, 0.8, 0), ("УЗБЕКИСТАН", 0.7, 0.8, 0), ("сообщаем", 0.8, 0.8, 0)],
        # yolg'iz katta harf (".Б." siz) — bosh harf emas: "В Министерство"
        [("В", 0.6, 0.8, 0), ("Министерство", 0.7, 0.8, 0)],
    ],
)
def test_given_name_rule_needs_caps_surname_on_same_line(items):
    assert choose_signer(candidates([page(1, items)])) is None


def test_lost_first_initial_is_marked_damaged():
    items = [("А", 0.6, 0.8, 0), (".Б.", 0.62, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)]
    split = candidates([page(1, items)])
    assert not split[0].damaged  # "А" ".Б." — ikkala bosh harf bor
    for first in (".Б.", ",Б."):
        lost = candidates([page(1, [(first, 0.62, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)])])
        assert lost[0].damaged and lost[0].latin() == "B.Sidorov"
    assert not candidates([page(1, [("А.Б.", 0.6, 0.8, 0), ("Сидоров", 0.7, 0.8, 0)])])[0].damaged
