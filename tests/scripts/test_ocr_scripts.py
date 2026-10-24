"""scripts/ocr testlari (make_crops, compare_ocr) — soxta xat bilan."""

import json
import re
import sys

from scripts.ocr import check_crops, compare_ocr, make_crops
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
    assert files == ["date.png", "header.png", "line.png", "number.png", "page.png"]
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


class FakeReader:
    def read(self, png: bytes) -> str:
        return '{"sana": "12.03.2026", "raqam": "55/07-1234"}'


def test_compare_adds_new_crops_to_saved_texts(tmp_path, monkeypatch, capsys):
    pdf = make_letter_pdf(tmp_path / "xat.pdf")
    (tmp_path / "crops" / "DOC_1").mkdir(parents=True)
    (tmp_path / "crops" / "DOC_1" / "number.png").write_bytes(b"png")
    out = tmp_path / "ocr"
    out.mkdir()
    (out / "vlm-extract.json").write_text(json.dumps({"DOC_1": {"header": "eski"}}))
    truth = {"rekvizit_document": {"hujjat_sana": "12.03.2026", "hujjat_raqami": "55/07-1234"}}
    monkeypatch.setattr(compare_ocr, "list_letters", lambda: [Letter("DOC_1", pdf, pdf)])
    monkeypatch.setattr(compare_ocr, "load_split", lambda: {"dev": ["DOC_1"], "test": []})
    monkeypatch.setattr(compare_ocr, "load_truth", lambda letter: truth)
    monkeypatch.setattr(compare_ocr, "get_pages", lambda letter: pages_of(letter.pdf))
    monkeypatch.setattr(compare_ocr, "make_reader", lambda name: FakeReader())
    monkeypatch.setattr(compare_ocr, "CROPS_DIR", tmp_path / "crops")
    monkeypatch.setattr(compare_ocr, "OUT_DIR", out)
    monkeypatch.setattr(sys, "argv", ["compare_ocr", "vlm-extract", "--crops", "number"])
    compare_ocr.main()

    saved = json.loads((out / "vlm-extract.json").read_text())
    assert saved["DOC_1"]["header"] == "eski"  # oldin o'qilgan bo'lak o'chmadi
    assert "55/07-1234" in saved["DOC_1"]["number"]  # yangisi qo'shildi
    assert "55/07" not in capsys.readouterr().out  # ekranga faqat sonlar


def test_compare_saved_texts_without_ocr(tmp_path, monkeypatch, capsys):
    pdf = make_letter_pdf(tmp_path / "xat.pdf")
    out = tmp_path / "ocr"
    out.mkdir()
    header = '{"sana": "12.03.2026", "raqam": "55/07-1234"}'
    saved = {"DOC_1": {"header": header}, "DOC_2": {"header": header}}
    (out / "vlm-extract.json").write_text(json.dumps(saved))
    truth = {"rekvizit_document": {"hujjat_sana": "12.03.2026", "hujjat_raqami": "55/07-1234"}}
    letters = [Letter("DOC_1", pdf, pdf), Letter("DOC_2", pdf, pdf)]
    monkeypatch.setattr(compare_ocr, "list_letters", lambda: letters)
    monkeypatch.setattr(compare_ocr, "load_split", lambda: {"dev": ["DOC_1", "DOC_2"]})
    monkeypatch.setattr(compare_ocr, "load_truth", lambda letter: truth)
    monkeypatch.setattr(compare_ocr, "get_pages", lambda letter: pages_of(letter.pdf))
    monkeypatch.setattr(compare_ocr, "make_reader", lambda name: 1 / 0)  # OCR chaqirilmasin
    monkeypatch.setattr(compare_ocr, "OUT_DIR", out)
    argv = ["compare_ocr", "vlm-extract", "--saved", "--crops", "header", "--ids", "DOC_2"]
    monkeypatch.setattr(sys, "argv", argv)
    compare_ocr.main()

    rows = capsys.readouterr().out
    assert "dev 1 xat" in rows  # faqat DOC_2
    assert re.search(r"raqam: header bo'lagi\s+1\s+1 /1", rows)  # 1 javob, 1 to'g'ri


def test_region_near_registry_office_wins():
    from scripts.boshqarma.measure_regions import choose_weighted
    from src.fields.boshqarma import choose_region, letter_regions
    from src.reading.pages import CachedPage
    from src.reading.pdf_text import PageText, Word

    def page(number, text):
        words = [Word(t, 0.1, 0.6, 0.2, 0.61, 0) for t in text.split()]
        return CachedPage(number, PageText(number, "text_layer", words), None)

    filler = "Просим истребовать повторное свидетельство и направить его в наш адрес. " * 2
    text = (
        "Запись акта о рождении составлена отделом ЗАГС Наманганской области. "
        f"{filler}Гражданин проживает: Андижанская область, г. Андижан."
    )
    pages = [page(1, "Просим оказать содействие"), page(2, text)]
    hits = letter_regions(pages, recipient_mode="drop", max_pages=6)
    assert choose_region(hits) == "andijon"  # ko'p eslatilgan
    assert choose_weighted(hits, pages, 80, 3, False, 1) == "namangan"  # ЗАГС yonidagi
