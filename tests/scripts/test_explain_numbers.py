"""explain_numbers testlari — to'qilgan raqamlar va OCR matnlari bilan."""

from scripts.ocr.explain_numbers import NOTHING, READ, SUGGESTED, WRITTEN, candidates, group_of
from tests.engine.test_predict import letter_with_blank


def test_candidates_collect_who_read_each_number():
    texts = {
        "vlm-extract": {"header": '{"raqam": "12/3-46"}'},
        "rapidocr": {"header": "№ 12/3-46", "line": "12/3-45"},
    }
    first = letter_with_blank("СОХТА ВАЗИРЛИК")[0]  # sahifada "№" yo'q — matndan raqam yo'q
    found = candidates(list(texts), texts, first)
    assert found["12/3-46"] == {("vlm-extract", "header"), ("rapidocr", "header")}
    assert found["12/3-45"] == {("rapidocr", "line")}


def test_group_of_each_place():
    found = {"12/3-46": set(), "12/3-45": set(), "99/9-1": set()}
    assert group_of("12/3-46", ["12/3-46"], found, "12/3-46") == (WRITTEN, None)
    assert group_of(None, ["12/3-45", "12/3-46"], found, "12/3-46") == (SUGGESTED[1], None)
    assert group_of(None, ["99/9-1"], found, "12/3-45") == (READ, None)
    assert group_of(None, [], {}, "12/3-46") == (NOTHING, None)
    group, nearest = group_of("12/3-45", ["12/3-45"], {"12/3-45": set()}, "12/3-47")
    assert (group, nearest) == ("hech qayerda: 1 belgi farq", "12/3-45")
