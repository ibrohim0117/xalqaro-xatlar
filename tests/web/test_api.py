"""src/web/api.py testlari — soxta xat, vaqtinchalik model va xotira fayllari bilan."""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.engine.date_ocr import DateReading
from src.engine.model import Model, save_model
from src.web.api import create_app, received_date
from tests.conftest import FAKE_LETTER, make_letter_pdf, needs_tesseract

FARGONA = "Farg'ona viloyati adliya boshqarmasi"
ARGENTINA = [(50, 60, "Ministerio de Justicia"), (50, 76, "Republica Argentina"), *FAKE_LETTER[2:]]
TRUTH = {
    "rekvizit_document": {"hujjat_raqami": "55/07-1234", "imzolagan_shaxs": "A.B.Sidorov"},
    "tasks": [{"asosiy_ijrochilar": [FARGONA]}],
}


def no_ocr():
    return None  # sana OCR'i o'chiq — testlar modelsiz va tez


@pytest.fixture
def client(tmp_path):
    save_model(Model(names={"fargona": FARGONA}, summary="Mazmun"), tmp_path / "model.json")
    return TestClient(
        create_app(tmp_path / "model.json", tmp_path / "feedback.jsonl", date_ocr_factory=no_ocr)
    )


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
    assert body["joylar"]["imzolagan_shaxs"][0]["sahifa"] == 1
    assert "rasmlar" not in body  # rasmlar faqat so'ralganda (javob yengil qolsin)


@needs_tesseract
def test_extract_with_page_images(client, letter_pdf):
    files = {"pdf": ("xat.pdf", letter_pdf.read_bytes(), "application/pdf")}
    body = client.post("/extract?rasmlar=true", files=files).json()
    assert len(body["rasmlar"]) == body["vaqt"]["sahifalar"] == 2
    assert body["rasmlar"][0].startswith("data:image/jpeg;base64,")


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
    app = create_app(tmp_path / "yoq.json", tmp_path / "feedback.jsonl", date_ocr_factory=no_ocr)
    client = TestClient(app)
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


def test_page_and_static_files_are_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert '<script type="module" src="/static/js/main.js"' in page.text
    for name in ("js/main.js", "js/single.js", "js/batch.js", "style.css"):
        assert client.get(f"/static/{name}").status_code == 200
    # ilova yangilanganda brauzer eski kodni keshdan ishlatmasin
    assert page.headers["cache-control"] == "no-cache"
    assert client.get("/static/js/main.js").headers["cache-control"] == "no-cache"
    # sahifa internetdan hech narsa yuklamaydi
    assert "http://" not in page.text and "https://" not in page.text


class FakeDateOcr:
    """Sana dvigateli o'rnida: kelgan sanani eslab qoladi, tayyor natija qaytaradi."""

    def __init__(self):
        self.received = None

    def read(self, page, first, received):
        self.received = received
        return DateReading(None, "12.03.2026", ["12.03.2026", "13.03.2026"], 1.5, ["vlm", "rapid"])


@needs_tesseract
def test_prefilled_date_with_suggestions(tmp_path):
    save_model(Model(names={"fargona": FARGONA}, summary="Mazmun"), tmp_path / "model.json")
    fake = FakeDateOcr()
    app = create_app(tmp_path / "model.json", tmp_path / "f.jsonl", date_ocr_factory=lambda: fake)
    pdf = make_letter_pdf(tmp_path / "xat.pdf").read_bytes()
    truth = json.dumps({"rekvizit_document": {"kirish_sana": "05.01.2026"}}).encode()
    body = upload(TestClient(app), pdf, truth).json()
    assert body["rekvizit_document"]["hujjat_sana"] == "12.03.2026"
    assert "hujjat_sana" in body["tekshirish_kerak"]  # yozildi, lekin "tekshiring"
    assert body["takliflar"]["hujjat_sana"] == ["12.03.2026", "13.03.2026"]
    assert body["vaqt"]["sana_ocr"] == 1.5 and body["vaqt"]["sana_ocrlar"] == ["vlm", "rapid"]
    assert fake.received == date(2026, 1, 5)  # kelgan sana json'dan (test rejimi)


def test_received_date_sources():
    truth = {"rekvizit_document": {"kirish_sana": "05.01.2026"}}
    assert received_date("09.01.2026", truth) == date(2026, 1, 9)  # so'rovdagisi ustun
    assert received_date(None, truth) == date(2026, 1, 5)
    assert received_date(None, None) == date.today()


def test_pages_without_ocr(client, letter_pdf):
    files = {"pdf": ("xat.pdf", letter_pdf.read_bytes(), "application/pdf")}
    body = client.post("/pages", files=files).json()
    assert len(body["rasmlar"]) == 2 and body["rasmlar"][0].startswith("data:image/jpeg;base64,")
    assert client.post("/pages", files={"pdf": ("x.pdf", b"bu pdf emas")}).status_code == 400
