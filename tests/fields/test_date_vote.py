"""src/fields/date_vote.py testlari — to'qilgan OCR matnlari bilan."""

from datetime import date

from src.fields.date_vote import (
    confirmed,
    engine_dates,
    header_anchor_date,
    in_window,
    ranked,
    vote,
)


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


def test_first_engine_needs_confirmation():
    vlm = engine_dates({"header": "УПРАВЛЕНИЕ\n12.03.2026 № 55/07"})  # "№" qatoridagi sana
    rapid_same = engine_dates({"line": "12.03.2026 No 55/07"})
    rapid_other = engine_dates({"date": "13.03.2026"})
    assert confirmed([vlm, rapid_same]) == "12.03.2026"  # boshqa OCR tasdiqladi
    assert confirmed([vlm, rapid_other]) is None  # tasdiqlanmadi — avtomatik emas


def test_stricter_confirmation():
    vlm = engine_dates({"date": "12.03.2026"})
    weak = engine_dates({"header": "Справка 12.03.2026"})  # faqat "header'dagi birinchi sana"
    strong = engine_dates({"date": "12.03.2026"})
    assert confirmed([vlm, weak]) == "12.03.2026"
    assert confirmed([vlm, weak], keys=("date", "header_anchor")) is None  # bo'sh manba hisob emas
    assert confirmed([vlm, strong, weak], min_others=2) == "12.03.2026"
    assert confirmed([vlm, strong], min_others=2) is None


def test_date_window_rejects_misread_year():
    received = date(2026, 1, 5)
    assert in_window("16.12.2025", received, 365)
    assert not in_window("16.12.2015", received, 365)  # yil xato o'qilgan — 10 yil oldin
    assert not in_window("16.02.2026", received, 365)  # kelgan kundan keyin bo'lishi mumkin emas
    assert in_window("16.12.2015", received, None)  # tekshiruv o'chiq
    assert not in_window(None, received, 365)
