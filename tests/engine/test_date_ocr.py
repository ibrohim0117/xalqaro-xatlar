"""src/engine/date_ocr.py testlari — soxta OCR'lar bilan (haqiqiy model kerak emas)."""

from datetime import date

import pymupdf
import pytest

from src.engine.date_ocr import DateOcr, DateReading, apply_reading, build_date_ocr
from tests.conftest import FAKE_LETTER, make_letter_pdf
from tests.engine.test_locate import pages_of

RECEIVED = date(2026, 4, 1)
NO_PRINTED_DATE = [  # sana qo'lda yozilgan — matn qatlamida faqat "№" va raqam
    line if "№" not in line[2] else (line[0], line[1], "№ 55/07-1234") for line in FAKE_LETTER
]


class FakeReader:
    """Har bo'lakka bir xil matn qaytaradi; kerak bo'lsa — ishlamay qoladi."""

    def __init__(self, name: str, text: str = "", broken: bool = False):
        self.name, self.text, self.broken, self.calls = name, text, broken, 0

    def read(self, png: bytes) -> str:
        self.calls += 1
        if self.broken:
            raise ConnectionError("server o'chiq")
        return self.text


@pytest.fixture
def letter(tmp_path):
    def make(lines):
        pdf = make_letter_pdf(tmp_path / "xat.pdf", lines)
        return pymupdf.open(pdf)[0], pages_of(pdf)[0]

    return make


def test_printed_date_is_automatic_and_ocr_is_skipped(letter):
    vlm = FakeReader("vlm", "01.01.2026")
    reading = DateOcr([vlm], confirm_first=True).read(*letter(FAKE_LETTER), RECEIVED)
    assert reading.auto == "12.03.2026" and reading.prefill is None
    assert vlm.calls == 0  # matn qatlamidan topildi — OCR vaqti tejaldi


def test_vlm_confirmed_by_another_ocr_is_prefilled(letter):
    readers = [FakeReader("vlm", "12.03.2026 № 55/07"), FakeReader("rapid", "12.03.2026 No 55")]
    reading = DateOcr(readers, confirm_first=True).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.auto is None
    assert reading.prefill == "12.03.2026"  # "tekshiring" belgisi bilan yoziladi
    assert reading.suggestions == ["12.03.2026"]
    assert reading.readers == ["vlm", "rapid"]


def test_disagreement_gives_only_suggestions(letter):
    readers = [FakeReader("vlm", "12.03.2026"), FakeReader("rapid", "13.03.2026")]
    reading = DateOcr(readers, confirm_first=True).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.prefill is None
    assert set(reading.suggestions) == {"12.03.2026", "13.03.2026"}


def test_misread_year_is_outside_the_window(letter):
    readers = [FakeReader("vlm", "12.03.2015"), FakeReader("rapid", "12.03.2015")]
    reading = DateOcr(readers, confirm_first=True).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.prefill is None and reading.suggestions == []


def test_broken_vlm_falls_back_to_vote(letter):
    readers = [
        FakeReader("vlm", broken=True),
        FakeReader("rapid", "12.03.2026"),
        FakeReader("tesseract", "12.03.2026"),
    ]
    reading = DateOcr(readers, confirm_first=True).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.readers == ["rapid", "tesseract"]  # VLM chetlandi
    assert reading.prefill == "12.03.2026"  # ikki OCR kelishdi (oddiy ovoz)


def answer_with(date_value=None, flags=("hujjat_sana", "hujjat_raqami")):
    return {
        "rekvizit_document": {"hujjat_sana": date_value},
        "tekshirish_kerak": list(flags),
        "takliflar": {"hujjat_sana": "01.01.2026"},
    }


def test_apply_prefill_keeps_the_flag():
    answer = answer_with()
    apply_reading(answer, DateReading(prefill="12.03.2026", suggestions=["12.03.2026"]))
    assert answer["rekvizit_document"]["hujjat_sana"] == "12.03.2026"
    assert "hujjat_sana" in answer["tekshirish_kerak"]
    assert answer["takliflar"]["hujjat_sana"] == ["12.03.2026"]  # bitta taklif o'rniga ro'yxat


def test_apply_auto_removes_the_flag_and_nothing_keeps_old_values():
    answer = answer_with()
    apply_reading(answer, DateReading(auto="12.03.2026"))
    assert "hujjat_sana" not in answer["tekshirish_kerak"]
    answer = answer_with()
    apply_reading(answer, DateReading())  # OCR hech narsa topmadi
    assert answer["rekvizit_document"]["hujjat_sana"] is None
    assert answer["takliflar"]["hujjat_sana"] == "01.01.2026"  # predict taklifi qoladi


def test_build_without_readers_is_off():
    assert build_date_ocr("") is None
    assert build_date_ocr("yoq-ocr") is None  # noma'lum nom — ogohlantirish bilan chetlanadi
