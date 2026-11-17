"""simulate_arrival testlari — to'qilgan blanklar, nomlar va raqamlar bilan."""

from datetime import date as Date

from scripts.rekvizit.simulate_arrival import (
    Item,
    arrival_order,
    grown,
    sender_outcome,
    template_outcome,
)
from src.engine.model import Model, learn_model, number_template
from src.engine.predict import predict
from src.fields.sender import SENDER_MODE, header_text
from tests.engine.test_predict import letter_with_blank

ARGENTINA = "Ministerio de Justicia de la República Argentina"
NOVO = "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ ПО НОВОСИБИРСКОЙ ОБЛАСТИ"


def item(doc_id: str, blank: str, sender: str, number: str, arrived: str | None) -> Item:
    pages = letter_with_blank(blank)
    doc = {"hujjat_junatuvchi_tashkilot": sender, "hujjat_raqami": number}
    if arrived:
        doc["kirish_sana"] = arrived
    return Item(doc_id, {"rekvizit_document": doc}, header_text(pages, SENDER_MODE), pages)


def test_arrival_order_by_date_then_doc_and_missing_last():
    items = [
        item("DOC_3", ARGENTINA, "A", "1", "02.03.2026"),
        item("DOC_1", ARGENTINA, "A", "1", None),
        item("DOC_2", ARGENTINA, "A", "1", "01.03.2026"),
        item("DOC_0", ARGENTINA, "A", "1", "02.03.2026"),
    ]
    assert [i.doc_id for i in arrival_order(items)] == ["DOC_2", "DOC_0", "DOC_3", "DOC_1"]
    assert items[2].arrived == Date(2026, 3, 1)


def test_sender_outcome_kinds_and_one_click():
    def answer(written, options):
        return {
            "rekvizit_document": {"hujjat_junatuvchi_tashkilot": written},
            "takliflar": {"hujjat_junatuvchi_tashkilot": options} if options else {},
        }

    assert sender_outcome(answer("Soxta Vazirlik", []), "soxta vazirlik") == ("to'g'ri", True)
    assert sender_outcome(answer("Boshqa", ["Soxta Vazirlik"]), "Soxta Vazirlik") == ("xato", True)
    assert sender_outcome(answer(None, ["Soxta Vazirlik"]), "Soxta Vazirlik") == (
        "yozilmadi",
        True,
    )
    assert sender_outcome(answer(None, None), "Soxta Vazirlik") == ("yozilmadi", False)


def test_grown_memory_recognizes_second_letter_and_learns_number_template():
    old = [item("DOC_1", NOVO, "Soxta Novosibirsk", "54/07-100", "01.01.2026")]
    base = learn_model([i.truth for i in old], [i.header for i in old])
    first = item("DOC_2", ARGENTINA, "Soxta Argentina", "12/3-45", "01.03.2026")
    second = item("DOC_3", ARGENTINA, "Soxta Argentina", "12/3-46", "02.03.2026")
    third = item("DOC_4", ARGENTINA, "Soxta Argentina", "12/3-47", "03.03.2026")

    answer = predict(second.pages, base)  # A: xotirada yo'q — yozilmaydi
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] is None
    model = grown(old, [first])  # B: birinchi xat tasdiqlangan
    answer = predict(second.pages, model)
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] == "Soxta Argentina"
    assert template_outcome(model, "Soxta Argentina", "12/3-46") == "qolip yo'q"  # 1 ta raqam

    model = grown(old, [first, second])  # 2 ta raqamdan qolip "9/9-9", bosh qism "12/3-"
    assert template_outcome(model, "Soxta Argentina", third.doc["hujjat_raqami"]) == "qolipga mos"
    assert template_outcome(model, "Soxta Argentina", "99/3-47") == "qolipga mos emas"
    assert template_outcome(model, None, "12/3-47") == "qolip yo'q"  # jo'natuvchi yozilmagan
    assert base.sender_names == ["Soxta Novosibirsk"]  # eski model o'zgarmadi


def test_template_outcome_without_templates():
    assert template_outcome(Model(), "Soxta Argentina", "12/3-47") == "qolip yo'q"


def test_number_outcome_and_shown():
    from scripts.rekvizit.simulate_arrival import number_outcome, shown
    from src.engine.number_ocr import NumberReading

    # bo'shliqsiz solishtiriladi (evaluate kabi)
    assert number_outcome(NumberReading("12/3 - 46", []), "12/3-46") == ("to'g'ri", True)
    assert number_outcome(NumberReading("12/3-46", []), "12/3-46") == ("to'g'ri", True)
    assert number_outcome(NumberReading("12/3-45", ["12/3-46"]), "12/3-46") == ("xato", True)
    assert number_outcome(NumberReading(None, []), "12/3-46") == ("yozilmadi", False)
    assert number_outcome(NumberReading("12/3-46", []), None) == ("xato", False)
    assert shown(("xato", True)) == "xato (taklifda)"
    assert shown(("to'g'ri", True)) == "to'g'ri"


def test_saved_reading_keeps_reader_order(tmp_path):
    import json

    from scripts.rekvizit.simulate_arrival import saved_reading

    texts = {"vlm-extract": {"header": '{"raqam": "12/3-46"}'}, "rapidocr": {"header": "№ 12/3-46"}}
    data = {"readers": list(texts), "texts": texts, "auto": None, "received": "01.03.2026"}
    (tmp_path / "DOC_1.json").write_text(json.dumps(data), encoding="utf-8")
    reading = saved_reading("DOC_1", (tmp_path / "yo'q", tmp_path))
    assert list(reading.texts) == ["vlm-extract", "rapidocr"]
    assert saved_reading("DOC_2", (tmp_path,)) is None


def test_template_fixes_number_read_by_ocr():
    from src.engine.date_ocr import DateReading
    from src.engine.number_ocr import read_number

    old = [item("DOC_1", NOVO, "Soxta Novosibirsk", "54/07-100", "01.01.2026")]
    earlier = [
        item("DOC_2", ARGENTINA, "Soxta Argentina", "12/3-45", "01.03.2026"),
        item("DOC_3", ARGENTINA, "Soxta Argentina", "12/3-46", "02.03.2026"),
    ]
    model = grown(old, earlier)
    texts = {"vlm-extract": {"header": '{"raqam": "12-3-47"}'}, "rapidocr": {"header": "№ 12-3-47"}}
    reading = DateReading(readers=list(texts), texts=texts)
    first = earlier[0].pages[0]
    assert read_number(first, reading, None).prefill == "12-3-47"  # qolipsiz: ajratgich xato
    template = number_template(model, "Soxta Argentina")
    assert read_number(first, reading, template).prefill == "12/3-47"  # qolip tuzatdi


def test_sender_detail_shows_only_numbers():
    from scripts.rekvizit.simulate_arrival import sender_detail

    old = [item("DOC_1", NOVO, "Soxta Novosibirsk", "54/07-100", "01.01.2026")]
    base = learn_model([i.truth for i in old], [i.header for i in old])
    letter = item("DOC_2", NOVO, "Soxta Novosibirsk", "54/07-101", "01.03.2026")
    answer = predict(letter.pages, base)
    detail = sender_detail(letter, base, answer)
    assert "1-o'rinda" in detail and "yozgan qoida chegara" in detail and "belgi YO'Q" in detail
    assert "Novosibirsk" not in detail  # nom chiqmaydi


def test_place_status_three_cases():
    from scripts.rekvizit.simulate_arrival import place_status

    pages = letter_with_blank(NOVO)
    assert place_status(pages, "Soxta Novosibirsk viloyati") == "joy mos"
    assert place_status(pages, "Soxta Gruziya vazirligi") == "joy boshqa"
    assert place_status(letter_with_blank("ГЛАВНОЕ УПРАВЛЕНИЕ"), "Soxta") == "joy topilmadi"


def test_other_fields_compare_boshqarma_and_summary():
    from scripts.rekvizit.simulate_arrival import other_fields

    letter = item("DOC_1", NOVO, "Soxta", "1/1", "01.01.2026")
    letter.truth["rekvizit_document"]["hujjatning_qisqacha_mazmuni"] = "Soxta mazmun"
    letter.truth["tasks"] = [{"asosiy_ijrochilar_boshqarmalari": ["Soxta boshqarma"]}]
    answer = {
        "rekvizit_document": {"hujjatning_qisqacha_mazmuni": "soxta mazmun"},
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": []}],
    }
    assert other_fields(answer, letter) == {"boshqarma": "yozilmadi", "mazmun": "to'g'ri"}
