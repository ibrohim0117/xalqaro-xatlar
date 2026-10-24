"""src/engine/number_ocr.py testlari — sana dvigateli o'qigan (to'qilgan) matnlar bilan."""

from src.engine.date_ocr import DateReading
from src.engine.number_ocr import NumberReading, apply_number, read_number
from src.fields.number_template import Template
from tests.conftest import FAKE_LETTER, make_letter_pdf
from tests.engine.test_locate import pages_of

# raqam qo'lda yozilgan: bosma qatorda faqat "№" (matn qatlamida raqam yo'q)
HANDWRITTEN = [line if "№" not in line[2] else (line[0], line[1], "№") for line in FAKE_LETTER]
TEMPLATE = Template("9/9-9", "55/07-")  # tashkilotning boshqa xatlaridan o'rganilgan


def first_page(tmp_path):
    return pages_of(make_letter_pdf(tmp_path / "xat.pdf", HANDWRITTEN))[0]


def reading(**texts):
    return DateReading(texts=texts)


def test_template_fixes_vlm_and_other_ocr_confirms(tmp_path):
    texts = reading(
        **{"vlm-extract": {"header": '{"sana": "12.03.2026", "raqam": "35/07-1234"}'}},
        rapidocr={"line": "12.03.2026 No 55/07-1234"},
    )
    found = read_number(first_page(tmp_path), texts, TEMPLATE)
    assert found.prefill == "55/07-1234"  # VLM bosh qismni xato o'qigan — qolip tuzatdi
    plain = read_number(first_page(tmp_path), texts, None)
    assert plain.prefill is None and set(plain.suggestions) == {"35/07-1234", "55/07-1234"}


def test_old_vlm_confirmation_does_not_count(tmp_path):
    texts = reading(
        **{"vlm-extract": {"header": '{"raqam": "55/07-1234"}'}},
        vlm={"line": "12.03.2026 № 55/07-1234"},
    )
    found = read_number(first_page(tmp_path), texts, TEMPLATE)
    assert found.prefill is None and found.suggestions == ["55/07-1234"]


def test_without_ocr_only_text_layer_suggestion(tmp_path):
    printed = pages_of(make_letter_pdf(tmp_path / "bosma.pdf"))[0]  # "№ 55/07-1234" bosma
    found = read_number(printed, None, TEMPLATE)
    assert found == NumberReading(None, ["55/07-1234"])


def test_apply_number_keeps_the_flag():
    answer = {"rekvizit_document": {}, "tekshirish_kerak": [], "takliflar": {}}
    apply_number(answer, NumberReading("55/07-1234", ["55/07-1234", "55/07-1284"]))
    assert answer["rekvizit_document"]["hujjat_raqami"] == "55/07-1234"
    assert answer["tekshirish_kerak"] == ["hujjat_raqami"]  # raqamni xodim doim ko'radi
    assert answer["takliflar"]["hujjat_raqami"] == ["55/07-1234", "55/07-1284"]
