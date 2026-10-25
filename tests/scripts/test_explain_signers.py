"""scripts/rekvizit/explain_signers.py testlari — to'qilgan imzo qatorlari bilan."""

from scripts.rekvizit.explain_signers import (
    before_initials,
    initials_elsewhere,
    initials_near,
    is_executor,
    json_shape,
    mask,
    rule_of,
    where_in_text,
    word_detail,
)
from src.fields.signer import find_signer
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word


def page_of(lines: list[tuple[float, float, str]]) -> list[CachedPage]:
    words = []
    for n, (x, y, text) in enumerate(lines):
        for k, token in enumerate(text.split()):
            words.append(Word(token, x + 0.08 * k, y, x + 0.08 * k + 0.07, y + 0.01, n))
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


def test_executor_below_the_signature_is_detected():
    pages = page_of([(0.6, 0.70, "А.Б. Сидоров"), (0.05, 0.90, "Исп. В.Г. Петрова")])
    chosen = find_signer(pages)  # hozirgi qoida — eng pastdagi; "Исп." chap yarmida — olinmaydi
    assert chosen.surname == "Сидоров" and not is_executor(pages, chosen)
    right = page_of([(0.6, 0.70, "А.Б. Сидоров"), (0.55, 0.90, "Исп. В.Г. Петрова")])
    assert is_executor(right, find_signer(right))  # o'ng yarmida bo'lsa — ijrochi olinadi


def test_where_the_surname_stands_and_in_which_shape():
    pages = page_of([(0.6, 0.80, "Сидоров Алексей Борисович")])
    assert where_in_text(pages, "Sidorov") == (1, "o'ng-past", "- Фамилия Имя Имя")
    ukraine = page_of([(0.6, 0.80, "Олена МЕЛЬНИЧУК")])
    assert where_in_text(ukraine, "Melnichuk") == (1, "o'ng-past", "Имя ФАМИЛИЯ - -")
    initials = page_of([(0.6, 0.80, "І.В. Петренко")])
    assert where_in_text(initials, "Petrenko") == (1, "o'ng-past", "И.О. Фамилия - -")
    assert where_in_text(pages, "Ivanov") is None


def test_lone_surname_reports_what_stands_before_it():
    pages = page_of([(0.3, 0.80, "Министр юстиции Сидоров")])
    found = where_in_text(pages, "Sidorov")
    shape = "- Фамилия - - [oldingi so'z: kichik harfli so'z 'к', yonida; familiya 'Кк']"
    assert found == (1, "chap-past", shape)
    assert [word_detail(t) for t in ("—", "12", "Minister", "юстиции")] == [
        "belgi",
        "raqam",
        "lotin",
        "kichik harfli so'z",
    ]


def test_initials_found_near_the_surname_in_any_shape():
    shapes = {
        "А.Б. Сидоров": ["A", "B"],
        "Сидоров А.Б.": ["A", "B"],
        "Е. П. Сидоров": ["E", "P"],
        "Алексей Борисович Сидоров": ["A", "B"],
        "Сидоров Алексей": ["A"],
        "министр Сидоров": None,
    }
    for text, expected in shapes.items():
        pages = page_of([(0.6, 0.8, text)])
        words = pages[0].main.words
        i = next(j for j, w in enumerate(words) if w.text == "Сидоров")
        assert initials_near(words, i) == expected, text


def test_initials_elsewhere_compares_with_json():
    pages = page_of([(0.1, 0.2, "Сидоров А.Б."), (0.6, 0.8, "министр Сидоров")])
    assert initials_elsewhere(pages, "Sidorov", ["A", "B"]).endswith("MOS")
    assert initials_elsewhere(pages, "Sidorov", ["A"]) == "xatda bor, mos emas"
    lone = page_of([(0.6, 0.8, "министр Сидоров")])
    assert initials_elsewhere(lone, "Sidorov", ["A"]) == "xatda bosh harfi bilan yo'q"


def test_json_shape_hides_the_name():
    assert json_shape("Xrushev O.N.") == "Aa A.A."
    assert json_shape("O.N.Xrushev") == "A.A.Aa"
    assert json_shape(None) == "bo'sh"


def test_rule_of_tells_which_rule_found_the_signer():
    russian = page_of([(0.6, 0.8, "А.Б. Сидоров")])
    assert rule_of(russian, find_signer(russian)) == "И.О."
    ukraine = page_of([(0.6, 0.8, "Олена МЕЛЬНИЧУК")])
    assert rule_of(ukraine, find_signer(ukraine)) == "Имя ФАМИЛИЯ"


def test_mask_shows_structure_without_letters():
    assert mask("А.Б.") == "К.К."
    assert mask("А.Б") == "К.К"
    assert mask("Rustam") == "Ll"
    assert mask("СИДОРОВ,") == "КК,"
    assert mask("Öwezow") == "?l"
    assert mask("12.05") == "9.9"


def test_before_initials_shows_where_the_lost_initial_stands():
    pages = page_of([(0.1, 0.80, "министр"), (0.6, 0.80, ".Б. Сидоров")])
    found = before_initials(pages, find_signer(pages))
    assert found == "imzo '.К. Кк', oldida: 'к' (boshqa qator, bir balandlikda)"
