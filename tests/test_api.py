"""src/api.py testlari — soxta xat, vaqtinchalik model va xotira fayllari bilan."""

import json

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.predict import Model, save_model
from tests.conftest import FAKE_LETTER, make_letter_pdf, needs_tesseract

FARGONA = "Farg'ona viloyati adliya boshqarmasi"
ARGENTINA = [(50, 60, "Ministerio de Justicia"), (50, 76, "Republica Argentina"), *FAKE_LETTER[2:]]
TRUTH = {
    "rekvizit_document": {"hujjat_raqami": "55/07-1234", "imzolagan_shaxs": "A.B.Sidorov"},
    "tasks": [{"asosiy_ijrochilar": [FARGONA]}],
}


@pytest.fixture
def client(tmp_path):
    save_model(Model(names={"fargona": FARGONA}, summary="Mazmun"), tmp_path / "model.json")
    return TestClient(create_app(tmp_path / "model.json", tmp_path / "feedback.jsonl"))


def upload(client, pdf: bytes, truth: bytes | None = None):
    files = {"pdf": ("xat.pdf", pdf, "application/pdf")}
    if truth is not None:
        files["truth"] = ("xat.json", truth, "application/json")
    return client.post("/extract", files=files)


@needs_tesseract
def test_extract_returns_answer_time_and_blank_id(client, letter_pdf):
    response = upload(client, letter_pdf.read_bytes())
    assert response.status_code == 200
    body = response.json()
    assert body["tasks"] == [{"asosiy_ijrochilar_boshqarmalari": [FARGONA]}]
    assert body["fayl"] == "xat.pdf"
    assert body["vaqt"]["sahifalar"] == 2
    assert 0 < body["vaqt"]["ocr"] <= body["vaqt"]["jami"]
    assert body["blank_id"] and "solishtirish" not in body


@needs_tesseract
def test_extract_with_truth_compares(client, letter_pdf):
    body = upload(client, letter_pdf.read_bytes(), json.dumps(TRUTH).encode()).json()
    assert body["solishtirish"]["boshqarma"]["mos"] is True
    assert body["solishtirish"]["imzolagan_shaxs"]["mos"] is True
    assert body["solishtirish"]["hujjat_raqami"]["taklif_mos"] is True


def test_bad_inputs_are_rejected_before_ocr(client):
    assert upload(client, b"bu pdf emas").status_code == 400
    assert upload(client, b"%PDF", b"{buzuq json").status_code == 400
    assert upload(client, b"%PDF", b"[1, 2]").status_code == 400
    assert client.post("/confirm", json={"blank_id": "yoq", "nom": "X"}).status_code == 404


def test_missing_model(tmp_path):
    client = TestClient(create_app(tmp_path / "yoq.json", tmp_path / "feedback.jsonl"))
    assert upload(client, b"%PDF").status_code == 503


@needs_tesseract
def test_confirmed_sender_is_recognized_next_time(client, tmp_path):
    pdf = make_letter_pdf(tmp_path / "argentina.pdf", ARGENTINA).read_bytes()
    first = upload(client, pdf).json()
    assert first["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] is None  # notanish

    blank_id = first["blank_id"]
    assert client.post("/confirm", json={"blank_id": blank_id, "nom": "  "}).status_code == 400
    name = "Argentina Respublikasi Adliya vazirligi"
    assert client.post("/confirm", json={"blank_id": blank_id, "nom": name}).status_code == 200

    second = upload(client, pdf).json()
    assert second["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] == name  # endi avtomatik
    assert len((tmp_path / "feedback.jsonl").read_text(encoding="utf-8").splitlines()) == 1
