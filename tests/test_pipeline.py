"""src/pipeline.py testlari — soxta xat va to'qilgan nomlar bilan."""

import pymupdf
import pytest

from src.feedback import confirm_sender
from src.pipeline import compare, current_model, process_pdf
from src.predict import Model, save_model
from tests.conftest import needs_tesseract

MODEL = Model(names={"fargona": "Farg'ona viloyati adliya boshqarmasi"}, summary="Mazmun")


@needs_tesseract
def test_process_pdf_from_bytes(letter_pdf):
    result = process_pdf(letter_pdf.read_bytes(), MODEL)
    answer, blank = result.answer, result.blank
    rekvizit = answer["rekvizit_document"]
    assert answer["tasks"] == [
        {"asosiy_ijrochilar_boshqarmalari": ["Farg'ona viloyati adliya boshqarmasi"]}
    ]
    assert rekvizit["imzolagan_shaxs"] == "A.B.Sidorov"
    assert rekvizit["hujjat_sana"] == "12.03.2026"
    assert answer["takliflar"]["hujjat_raqami"] == "55/07-1234"
    assert "hujjat_junatuvchi_tashkilot" in answer["tekshirish_kerak"]  # modelda jo'natuvchi yo'q
    assert "УПРАВЛЕНИЕ ЮСТИЦИИ" in blank  # /confirm uchun blank
    assert "Просим" not in blank  # xat matni blankka kirmaydi
    assert result.pages == 2
    assert result.ocr.calls >= 2  # 1-sahifa har doim, 2-sahifada matn qatlami yo'q
    assert 0 < result.ocr.seconds <= result.seconds


@pytest.mark.parametrize("data", [b"", b"bu pdf emas"])
def test_not_a_pdf(data):
    with pytest.raises(pymupdf.FileDataError):
        process_pdf(data, MODEL)


def test_current_model_adds_confirmed_senders(tmp_path):
    model_file, feedback_file = tmp_path / "model.json", tmp_path / "feedback.jsonl"
    save_model(MODEL, model_file)
    assert current_model(model_file, feedback_file).sender_names == []  # hali tasdiq yo'q
    confirm_sender("Ministerio de Justicia Argentina", "Argentina AV", feedback_file)
    assert current_model(model_file, feedback_file).sender_names == ["Argentina AV"]


def test_compare_marks_correct_wrong_and_suggestions():
    answer = {
        "rekvizit_document": {
            "hujjat_junatuvchi_tashkilot": None,
            "hujjat_sana": "12.03.2026",
            "hujjat_raqami": None,
            "imzolagan_shaxs": "A.B. Sidorov",
            "hujjatning_qisqacha_mazmuni": "Mazmun",
        },
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": ["Farg'ona viloyati adliya boshqarmasi"]}],
        "takliflar": {"hujjat_raqami": "55/07-1234", "hujjat_junatuvchi_tashkilot": ["A", "B AV"]},
    }
    truth = {
        "rekvizit_document": {
            "hujjat_junatuvchi_tashkilot": "B AV",
            "hujjat_sana": "13.03.2026",
            "hujjat_raqami": "55/07-1234",
            "imzolagan_shaxs": "A.B.Sidorov",
            "hujjatning_qisqacha_mazmuni": "Boshqa mazmun",
        },
        "tasks": [{"asosiy_ijrochilar": ["Farg'ona viloyati adliya boshqarmasi"]}],
    }
    rows = compare(answer, truth)
    assert rows["imzolagan_shaxs"]["mos"] is True  # bo'shliq farqi hisobga olinmaydi
    assert rows["hujjat_sana"]["mos"] is False
    assert rows["hujjatning_qisqacha_mazmuni"]["mos"] is False
    assert rows["boshqarma"]["mos"] is True  # viloyat asosiy_ijrochilar da (evaluate qoidasi)
    assert rows["hujjat_raqami"] == {
        "ai": None,
        "togri": "55/07-1234",
        "mos": None,  # AI yozmagan — "tekshirish kerak", xato emas
        "taklif_mos": True,
    }
    assert rows["hujjat_junatuvchi_tashkilot"]["taklif_mos"] is True  # variantlardan biri to'g'ri
