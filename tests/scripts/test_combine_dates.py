"""scripts/ocr/combine_dates.py testlari — to'qilgan OCR matnlari bilan."""

from scripts.ocr.combine_dates import engine_dates, header_anchor_date, ranked, vote


def test_vote_needs_two_engines_and_a_clear_winner():
    assert vote([{"12.03.2026"}, {"12.03.2026"}, {"01.01.2026"}]) == "12.03.2026"
    assert vote([{"12.03.2026"}, {"01.01.2026"}]) is None  # kelishmadi
    assert vote([{"12.03.2026"}, {"01.01.2026"}], min_votes=1) is None  # teng — tanlanmaydi
    assert vote([{"12.03.2026", "01.01.2026"}, set()], min_votes=1) is None
    assert vote([set(), set()]) is None


def test_one_engine_is_one_vote_even_with_two_crops():
    # bitta OCR date va header'dan bir xil sana o'qisa ham — bitta ovoz
    found = engine_dates({"date": "12.03.2026", "header": "12.03.2026 № 55/07"})
    assert vote([{d for d in found.values() if d}]) is None


def test_header_anchor_date_prefers_number_line():
    header = "Справка от 01.01.2025\nУПРАВЛЕНИЕ 05.05.2025\n12.03.2026 No 55/07-1234"
    assert header_anchor_date(header) == "12.03.2026"  # "№" (No) qatoridagi sana
    assert header_anchor_date("УПРАВЛЕНИЕ 05.05.2025") is None
    assert (
        engine_dates({"header": header})["header_first"] == "05.05.2025"
    )  # "от" dan keyingisi emas


def test_ranked_suggestions():
    engines = [{"12.03.2026", "01.01.2026"}, {"12.03.2026"}, {"05.05.2025"}]
    assert ranked(engines)[0] == "12.03.2026"  # ikki OCR ko'rgan — birinchi
    assert set(ranked(engines)) == {"12.03.2026", "01.01.2026", "05.05.2025"}
    assert len(ranked(engines, k=2)) == 2
