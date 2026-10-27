"""scripts/ocr/compare_date_rules.py testlari — to'qilgan sanalar bilan."""

from datetime import date

from scripts.ocr.compare_date_rules import (
    AMBIGUOUS,
    Case,
    load_saved,
    rival,
    rule_a,
    rule_b,
    rule_c,
    rule_d,
    suggestions,
    written_by,
)
from scripts.prototype.measure_time import save_reading
from src.engine.date_ocr import DateReading

READERS = ["vlm-extract", "vlm", "rapidocr", "rapidocr-eslav", "tesseract-block", "apple-vision"]
TRUE, WRONG, OTHER = "17.01.2026", "11.01.2026", "05.01.2026"


def seen(**dates) -> dict[str, str | None]:
    """Bitta OCR'ning nomzodlari (date_vote.engine_dates shakli)."""
    keys = ("date", "line", "header_anchor", "header_first", "page")
    return {key: dates.get(key) for key in keys}


def test_vlm_confirming_itself_against_independent_ocrs():
    # 27.10 holati: VLM ikki savolda bir xil xato kun, mustaqillar — to'g'ri sana
    found = [
        seen(header_first=WRONG, page=WRONG),
        seen(header_anchor=WRONG, header_first=WRONG),
        seen(header_first=TRUE),
        seen(header_first=TRUE),
        seen(),
        seen(header_first=TRUE, page=TRUE),
    ]
    assert rule_a(READERS, found) == WRONG  # hozirgi: VLM o'zini o'zi tasdiqladi
    assert rule_b(READERS, found) is None  # mustaqil tasdiq yo'q
    assert rule_c(READERS, found) is None  # mustaqillar boshqa sanaga kelishgan — yozilmaydi
    assert rule_d(READERS, found) == TRUE  # ziddiyatda mustaqillar sanasi


def test_independent_confirmation_keeps_every_rule_writing():
    found = [seen(header_first=TRUE), seen(), seen(line=TRUE), seen(), seen(), seen()]
    assert {rule(READERS, found) for rule in (rule_a, rule_b, rule_c, rule_d)} == {TRUE}


def test_only_the_second_vlm_question_confirms():
    found = [seen(header_first=TRUE), seen(header_first=TRUE), seen(), seen(), seen(), seen()]
    assert rule_a(READERS, found) == rule_c(READERS, found) == rule_d(READERS, found) == TRUE
    assert rule_b(READERS, found) is None  # B: VLM'ning ikkinchi savoli tasdiq emas


def test_two_rivals_with_equal_votes_are_ambiguous():
    found = [
        seen(header_first=WRONG),
        seen(header_first=WRONG),
        seen(header_first=TRUE),
        seen(header_first=TRUE),
        seen(header_first=OTHER),
        seen(header_first=OTHER),
    ]
    assert rival(READERS, found, WRONG) == AMBIGUOUS
    assert rule_c(READERS, found) is None and rule_d(READERS, found) is None


def test_suggestions_count_the_vlm_once_when_asked():
    found = [seen(header_first=WRONG), seen(header_first=WRONG), seen(header_first=TRUE)]
    found += [seen(), seen(), seen(header_first=TRUE)]
    assert suggestions(READERS, found) == [WRONG, TRUE]  # 2 va 2 ovoz — OCR tartibi
    assert suggestions(READERS, found, one_vlm=True) == [TRUE, WRONG]  # VLM 1, mustaqillar 2


def test_printed_date_wins_in_every_rule():
    case = Case("DOC_1", TRUE, TRUE, READERS, [seen(header_first=WRONG)] * 6)
    assert {written_by(case, rule) for rule in (rule_a, rule_b, rule_c, rule_d)} == {TRUE}


def test_saved_reading_round_trip(tmp_path):
    reading = DateReading(
        None, WRONG, [WRONG], 1.0, ["vlm-extract"], {"vlm-extract": {"header": "x"}}
    )
    save_reading(tmp_path / "ocr" / "DOC_1.json", reading, date(2026, 1, 20))
    readers, texts, auto, received = load_saved(tmp_path / "ocr" / "DOC_1.json")
    assert (readers, texts, auto, received) == (
        ["vlm-extract"],
        {"vlm-extract": {"header": "x"}},
        None,
        "20.01.2026",
    )
