"""src/engine/signer_ocr.py — imzo uchun Vision zaxirasi (soxta Vision, to'qilgan ismlar)."""

import pymupdf
import pytest

from src.engine.date_ocr import DateOcr
from src.engine.model import Model
from src.engine.pipeline import process_pdf
from src.engine.signer_ocr import apply_signer, needs_vision, vision_fallback, vision_signer
from src.fields.signer import Candidate
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word
from tests.conftest import FAKE_LETTER, make_letter_pdf, needs_tesseract

# pastki yarmi ichida (0..1): imzo sahifaning 0.83 balandligida, o'ng yarmida
SIGNATURE = [(0.66, 0.67, 0.02, 0.20, "А.Б. Сидоров")]


class FakeVision:
    name = "apple-vision"

    def __init__(self, found=SIGNATURE, broken=False):
        self.found, self.broken = found, broken

    def read(self, png: bytes) -> str:
        return ""

    def observations(self, png: bytes):
        if self.broken:
            raise RuntimeError("Vision ishlamadi")
        return self.found


def pages_with(signature: str) -> list[CachedPage]:
    tokens = enumerate(signature.split())
    words = [Word(t, 0.6 + 0.06 * i, 0.83, 0.65 + 0.06 * i, 0.84, 0) for i, t in tokens]
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


@pytest.fixture
def blank_page():
    doc = pymupdf.open()
    yield doc.new_page(width=595, height=842)
    doc.close()


def test_needs_vision():
    damaged = Candidate(1, 0.6, 0.8, ("Б",), "Сидоров", damaged=True)
    assert needs_vision(None) and needs_vision(damaged)
    assert not needs_vision(Candidate(1, 0.6, 0.8, ("А", "Б"), "Сидоров"))


def test_vision_signer_reads_the_lower_half(blank_page):
    found = vision_signer(blank_page, FakeVision())
    assert found.latin() == "A.B.Sidorov" and found.y0 == pytest.approx(0.83)


def test_fallback_only_when_text_signature_is_missing_or_damaged(blank_page):
    signer, repaired = vision_fallback(blank_page, pages_with(".Б. Сидоров"), FakeVision())
    assert signer.latin() == "A.B.Sidorov" and repaired  # bosh harf tiklandi
    signer, repaired = vision_fallback(blank_page, pages_with("Просим"), FakeVision())
    assert not repaired  # matn qoidasi umuman topmagan edi
    assert vision_fallback(blank_page, pages_with("А.Б. Сидоров"), FakeVision()) is None
    assert vision_fallback(blank_page, pages_with(".Б. Сидоров"), None) is None  # Vision yo'q
    broken = FakeVision(broken=True)
    assert vision_fallback(blank_page, pages_with(".Б. Сидоров"), broken) is None


def test_apply_signer_flags():
    def answer():
        return {"rekvizit_document": {"imzolagan_shaxs": "B.Sidorov"}, "tekshirish_kerak": []}

    good = Candidate(1, 0.6, 0.8, ("А", "Б"), "Сидоров")
    repaired = answer()
    repaired["tekshirish_kerak"].append("imzolagan_shaxs")
    apply_signer(repaired, good, repaired=True)
    assert repaired["rekvizit_document"]["imzolagan_shaxs"] == "A.B.Sidorov"
    assert repaired["tekshirish_kerak"] == []  # buzilgan imzo tuzatildi — belgi olib tashlandi
    new = answer()
    apply_signer(new, good, repaired=False)
    assert new["tekshirish_kerak"] == ["imzolagan_shaxs"]  # matn qoidasi topmagan — tekshiriladi


@needs_tesseract
def test_pipeline_repairs_a_damaged_signature(tmp_path):
    damaged = {"А.Б. Сидоров": ".Б. Сидоров"}  # PDF matnida birinchi bosh harf yo'qolgan
    lines = [(x, y, damaged.get(text, text)) for x, y, text in FAKE_LETTER]
    pdf = make_letter_pdf(tmp_path / "xat.pdf", lines)
    model = Model(names={"fargona": "Farg'ona viloyati adliya boshqarmasi"}, summary="Mazmun")
    without = process_pdf(pdf.read_bytes(), model)
    assert without.answer["rekvizit_document"]["imzolagan_shaxs"] == "B.Sidorov"
    assert "imzolagan_shaxs" in without.answer["tekshirish_kerak"]
    result = process_pdf(pdf.read_bytes(), model, DateOcr([FakeVision()]))
    assert result.answer["rekvizit_document"]["imzolagan_shaxs"] == "A.B.Sidorov"
    assert "imzolagan_shaxs" not in result.answer["tekshirish_kerak"]
    assert result.boxes["imzolagan_shaxs"][0]["y0"] == pytest.approx(0.83)
