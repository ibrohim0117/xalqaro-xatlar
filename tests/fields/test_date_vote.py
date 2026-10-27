"""src/fields/date_vote.py testlari — to'qilgan OCR matnlari bilan."""

from datetime import date

from src.fields.date_vote import (
    confirmed,
    engine_dates,
    fix_year,
    header_anchor_date,
    in_window,
    only_candidate,
    prefill_date,
    ranked,
    rival_dates,
    same_model,
    self_confirmed,
    vote,
    windowed,
)

READERS = ["vlm-extract", "vlm", "rapidocr", "rapidocr-eslav", "tesseract-block", "apple-vision"]
RIGHT, WRONG_DAY = "17.01.2026", "11.01.2026"


def seen(**dates) -> dict[str, str | None]:
    keys = ("date", "line", "header_anchor", "header_first", "page")
    return {key: dates.get(key) for key in keys}


# 27.10 holati (to'qilgan sanalar): VLM'ning ikki savoli bir xil xato kun, mustaqillar — to'g'ri
VLM_AGAINST_OTHERS = [
    seen(header_first=WRONG_DAY, page=WRONG_DAY),
    seen(header_anchor=WRONG_DAY, header_first=WRONG_DAY),
    seen(header_first=RIGHT),
    seen(header_first=RIGHT),
    seen(),
    seen(header_first=RIGHT, page=RIGHT),
]


def test_vlm_questions_are_one_model():
    assert same_model("vlm-extract", "vlm")
    assert not same_model("vlm-extract", "rapidocr") and not same_model("rapidocr", "apple-vision")


def test_independent_ocrs_agreeing_on_another_date_stop_the_prefill():
    assert rival_dates(VLM_AGAINST_OTHERS, READERS, WRONG_DAY) == [(RIGHT, 3)]
    assert prefill_date(VLM_AGAINST_OTHERS, "vlm-extract") == WRONG_DAY  # eski qoida (readers'siz)
    assert prefill_date(VLM_AGAINST_OTHERS, "vlm-extract", READERS) is None  # ziddiyat — yozilmaydi
    assert ranked([set(f.values()) - {None} for f in VLM_AGAINST_OTHERS])[0] == RIGHT  # taklifda


def test_no_conflict_keeps_the_prefill():
    one_other = [seen(header_first=RIGHT), seen(), seen(line=RIGHT), seen(header_first=WRONG_DAY)]
    one_other += [seen(), seen()]  # boshqa sanani faqat 1 mustaqil OCR ko'rgan — ziddiyat emas
    assert prefill_date(one_other, "vlm-extract", READERS) == RIGHT
    # boshqa sanani 2 mustaqil ko'rgan, lekin yozilajak sanani ham 2 tasi — ustun emas
    tied = [seen(header_first=RIGHT), seen(), seen(line=RIGHT), seen(line=RIGHT, page=WRONG_DAY)]
    tied += [seen(header_first=WRONG_DAY), seen()]
    assert prefill_date(tied, "vlm-extract", READERS) == RIGHT


def test_second_vlm_question_is_not_counted_as_independent_rival():
    found = [
        seen(header_first=RIGHT),
        seen(header_first=WRONG_DAY, date=WRONG_DAY),
        seen(line=RIGHT),
        seen(),
        seen(),
        seen(header_first=WRONG_DAY),
    ]  # boshqa sana: VLM ikkinchi savoli + 1 mustaqil — ziddiyatga yetmaydi
    assert rival_dates(found, READERS, RIGHT) == []
    assert prefill_date(found, "vlm-extract", READERS) == RIGHT


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


def test_self_confirmation_needs_two_different_crops():
    both = engine_dates({"line": "12.03.2026 № 55", "header": "УПРАВЛЕНИЕ\n12.03.2026 № 55"})
    assert self_confirmed([both]) == "12.03.2026"
    only_header = engine_dates({"header": "УПРАВЛЕНИЕ\n12.03.2026 № 55"})
    assert self_confirmed([only_header]) is None  # bitta bo'lak — tasdiq emas
    differ = engine_dates({"line": "12.03.2026", "header": "13.03.2026"})
    assert self_confirmed([differ]) is None


def test_only_candidate():
    one = [engine_dates({"header": "12.03.2026"}), engine_dates({"date": "12.03.2026"})]
    assert only_candidate(one) == "12.03.2026"
    two = [engine_dates({"header": "12.03.2026"}), engine_dates({"date": "13.03.2026"})]
    assert only_candidate(two) is None
    assert only_candidate([engine_dates({})]) is None


def test_first_engine_date_from_chosen_crops():
    # "aniq savol" VLM'i (vlm-extract) JSON beradi: unda "№" yo'q — sana header'dagi birinchi sana
    extract = engine_dates({"header": '{"sana": "12.03.2026", "raqam": "55/07"}'})
    rapid = engine_dates({"line": "12.03.2026 No 55/07"})
    assert confirmed([extract, rapid]) is None  # standart: faqat date va "№" qatori
    assert confirmed([extract, rapid], first_keys=("header_anchor", "header_first")) == "12.03.2026"


def test_self_confirmation_with_whole_page():
    found = engine_dates({"header": '{"sana": "12.03.2026"}', "page": '{"sana": "12.03.2026"}'})
    assert found["page"] == "12.03.2026"
    assert self_confirmed([found]) is None  # standart: date/line bilan solishtiriladi
    assert self_confirmed([found], others=("line", "page")) == "12.03.2026"


def test_fix_year_keeps_day_and_month_and_picks_the_year_in_the_window():
    received = date(2026, 3, 20)
    assert fix_year("12.03.2026", received, 365) == "12.03.2026"  # oynada — o'zi
    assert fix_year("12.03.2016", received, 365) == "12.03.2026"  # yil xato o'qilgan
    assert fix_year("12.03.2027", received, 365) == "12.03.2026"  # kelajakdagi yil
    assert fix_year("25.12.2016", received, 365) == "25.12.2025"  # o'tgan yil oxiri
    assert fix_year("25.06.2016", received, 120) is None  # 0..120 kunga tushmaydi
    assert fix_year("20.03.2016", received, 365) is None  # 2026 ham, 2025 ham oynada — noaniq
    assert fix_year("31.02.2016", received, 365) is None  # bunday sana yo'q
    assert fix_year("12.03.2016", None, 365) == "12.03.2016"  # kelgan sana yo'q — tekshiruvsiz
    assert fix_year(None, received, 365) is None


def test_windowed_fixes_years_and_drops_the_rest():
    received = date(2026, 3, 20)
    found = {"header": "12.03.2016", "date": "12.03.2026", "page": None, "line": "25.06.2016"}
    assert windowed(found, received, 120) == {
        "header": "12.03.2026",
        "date": "12.03.2026",
        "page": None,
        "line": None,
    }
