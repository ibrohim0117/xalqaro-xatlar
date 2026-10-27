"""scripts/prototype/measure_time.py testlari — soxta xat va soxta OCR bilan."""

from collections import defaultdict
from datetime import date

from scripts.prototype.measure_time import (
    CUT,
    Timed,
    changed_fields,
    tagged_crops,
    tips_difference,
)
from src.engine import date_ocr
from src.engine.date_ocr import DateOcr
from src.engine.model import Model
from src.engine.pipeline import process_pdf
from tests.conftest import needs_tesseract

MODEL = Model(names={"fargona": "Farg'ona viloyati adliya boshqarmasi"}, summary="Mazmun")


class FakeReader:
    """To'qilgan OCR: har bo'lakda bir xil matn."""

    name = "soxta"

    def read(self, png: bytes) -> str:
        return "12.03.2026 № 55/07-1234"


@needs_tesseract
def test_timing_does_not_change_the_answer_and_names_the_crops(letter_pdf):
    plain = process_pdf(letter_pdf.read_bytes(), MODEL, DateOcr([FakeReader()]), date(2026, 3, 20))
    log = defaultdict(float)
    with tagged_crops(log):
        timed = DateOcr([Timed(FakeReader(), log)])
        measured = process_pdf(letter_pdf.read_bytes(), MODEL, timed, date(2026, 3, 20))
    assert measured.answer == plain.answer  # o'lchagich javobga ta'sir qilmaydi
    crops = {"date", "line", "header"}  # noma'lum OCR o'qiydigan bo'laklar (date_ocr.CROPS)
    assert set(log) == {("soxta", c) for c in crops} | {(CUT, c) for c in crops}
    assert all(seconds >= 0 for seconds in log.values())
    assert date_ocr.crop_png.__module__ == "src.reading.crops"  # asli tiklandi


def test_changed_fields_gives_only_names():
    a = {
        "rekvizit_document": {"hujjat_sana": "12.03.2026", "hujjat_raqami": "55/07-1234"},
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": ["X"]}],
        "tekshirish_kerak": ["hujjat_raqami"],
        "takliflar": {"hujjat_raqami": ["55/07-1234"]},
    }
    assert changed_fields(a, a) == []
    b = {
        **a,
        "rekvizit_document": {"hujjat_sana": "13.03.2026", "hujjat_raqami": "55/07-1234"},
        "takliflar": {},
    }
    assert changed_fields(a, b) == [
        "hujjat_sana",
        "takliflar.hujjat_raqami (tarkib: umumiy 0, 1 va 0 ta)",
    ]
    assert changed_fields(a, {**a, "tasks": []}) == ["boshqarma"]


def test_tips_difference_tells_order_from_content_without_values():
    assert tips_difference(["05.03.2026", "07.03.2026"], ["07.03.2026", "05.03.2026"]) == (
        "faqat tartib"
    )
    assert (
        tips_difference(
            ["05.03.2026", "07.03.2026", "09.03.2026"], ["05.03.2026", "07.03.2026", "11.03.2026"]
        )
        == "tarkib: umumiy 2, 3 va 3 ta"
    )  # ovozi teng 3-o'rin boshqa chiqqan
    assert tips_difference("55/07", None) == "tarkib: umumiy 0, 1 va 0 ta"  # predict: bitta qiymat
