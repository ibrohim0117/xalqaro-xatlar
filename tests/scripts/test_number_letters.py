"""number_letters testlari — to'qilgan raqamlar bilan."""

from scripts.ocr.number_letters import MAPPINGS, Case, alphabet, homoglyph, reading, transliterate


def test_letter_mappings():
    assert homoglyph("12-ВН/И") == "12-BH/И"  # И ning lotincha o'xshashi yo'q
    assert transliterate("12-ВН/И") == "12-VN/I"
    assert MAPPINGS["aralash"]("12-ВН/И") == "12-BH/I"
    assert MAPPINGS["o'zgarishsiz"]("12-И") == "12-И"


def test_alphabet():
    assert alphabet("54/07-16606") == "harfsiz"
    assert alphabet("12-I/34") == "lotin"
    assert alphabet("12-И/34") == "kirill"
    assert alphabet("АB-1") == "ikkalasi"


def test_reading_maps_letters_before_vote():
    found = [{"header": "12-И/34"}, {"header": "12-I/34"}]
    case = Case("DOC_1", "12-I/34", ["vlm-extract", "rapidocr"], found, {}, None)
    assert reading(case, MAPPINGS["o'zgarishsiz"]).prefill is None  # kelishmadi
    assert reading(case, MAPPINGS["transliteratsiya"]).prefill == "12-I/34"  # endi kelishdi
