"""scripts/ocr testlari (make_crops, compare_ocr) — soxta xat bilan."""

import json

from scripts.ocr import check_crops, make_crops
from scripts.ocr.compare_ocr import answers
from src.evaluation.dataset import Letter
from tests.conftest import make_letter_pdf
from tests.engine.test_locate import pages_of


def test_main_writes_crops_and_manifest(tmp_path, monkeypatch, capsys):
    pdf = make_letter_pdf(tmp_path / "xat.pdf")
    monkeypatch.setattr(make_crops, "list_letters", lambda: [Letter("DOC_1", pdf, pdf)])
    monkeypatch.setattr(make_crops, "load_split", lambda: {"dev": ["DOC_1"], "test": []})
    monkeypatch.setattr(make_crops, "get_pages", lambda letter: pages_of(letter.pdf))
    monkeypatch.setattr(make_crops, "OUT_DIR", tmp_path / "crops")
    make_crops.main()

    files = sorted(p.name for p in (tmp_path / "crops" / "DOC_1").iterdir())
    assert files == ["date.png", "header.png", "line.png", "number.png"]
    manifest = json.loads((tmp_path / "crops" / "manifest.json").read_text())
    assert manifest["DOC_1"]["langar"] == "matn qatlami"
    assert "line 1" in capsys.readouterr().out  # bo'laklar soni ekranda


def test_compare_answers_from_crop_texts():
    texts = {"date": "30.09.26", "number": "№ 3-3-28/16847", "line": "30.09.26 № 3-3-28/16847"}
    found = answers(texts, text_layer_date=None)
    assert found["sana: date bo'lagi"] == found["sana: line bo'lagi"] == "30.09.2026"
    assert found["raqam: number bo'lagi"] == found["raqam: line bo'lagi"] == "3-3-28/16847"
    assert answers(texts, text_layer_date="01.01.2026")["sana: yangi qoida"] == "01.01.2026"
    assert answers({}, text_layer_date=None)["raqam: number bo'lagi"] is None  # bo'lak yo'q
    header = {"header": "Справка от 01.01.2025\n12.03.2026 № 55/07"}  # "от" dan keyingisi emas
    assert answers(header, text_layer_date=None)["sana: header bo'lagi"] == "12.03.2026"
    assert answers(header, text_layer_date=None)["sana: yangi qoida + header"] == "12.03.2026"


def test_check_crops_runs_on_a_letter(tmp_path, monkeypatch, capsys):
    pdf = make_letter_pdf(tmp_path / "xat.pdf")
    monkeypatch.setattr(check_crops, "list_letters", lambda: [Letter("DOC_1", pdf, pdf)])
    monkeypatch.setattr(check_crops, "load_split", lambda: {"dev": ["DOC_1"], "test": []})
    monkeypatch.setattr(check_crops, "get_pages", lambda letter: pages_of(letter.pdf))
    check_crops.main()
    out = capsys.readouterr().out
    # soxta xatda "12.03.2026 № 55/07-1234": sana ham, raqam ham o'z bo'lagida
    assert "matn qatlami  sana                    1               1                1" in out
    assert "matn qatlami  raqam                   1               1                1" in out
