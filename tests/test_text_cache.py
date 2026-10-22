"""src/text_cache.py testlari — soxta xatlar bilan, kesh vaqtinchalik papkada."""

import json

from src import text_cache
from src.dataset import Letter
from src.text_cache import extract_pages, get_pages, load, save
from tests.conftest import needs_tesseract


@needs_tesseract
def test_extract_ocrs_first_page_and_pages_without_text_layer(letter_pdf):
    first, second = extract_pages(letter_pdf)
    assert first.ocr is not None  # 1-sahifa matn qatlami bo'lsa ham OCR qilinadi
    assert first.main.source == "text_layer"  # lekin asosiy matn — matn qatlami
    assert second.ocr is not None  # 2-sahifada 50 belgidan kam — matn qatlami yo'q deb olinadi
    assert second.main.source == "ocr"


@needs_tesseract
def test_extract_scanned_pdf_uses_ocr_everywhere(scanned_pdf):
    assert [page.main.source for page in extract_pages(scanned_pdf)] == ["ocr", "ocr"]


@needs_tesseract
def test_save_and_load_give_the_same_pages(letter_pdf, tmp_path):
    pages = extract_pages(letter_pdf)
    path = tmp_path / "kesh.json"
    save(pages, path)
    assert load(path) == pages


def test_load_ignores_missing_broken_and_old_files(tmp_path):
    assert load(tmp_path / "yoq.json") is None
    old = tmp_path / "eski.json"
    old.write_text(json.dumps({"version": 0, "pages": []}))
    assert load(old) is None
    broken = tmp_path / "buzuq.json"
    broken.write_text('{"version": 1, "pages": [{"numb')  # yozish o'rtasida to'xtatilgandek
    assert load(broken) is None


@needs_tesseract
def test_get_pages_reads_pdf_only_once(letter_pdf, tmp_path, monkeypatch):
    letter = Letter("DOC_SOXTA", letter_pdf, tmp_path / "javob.json")
    first = get_pages(letter, cache_dir=tmp_path)
    assert (tmp_path / "DOC_SOXTA.json").exists()

    def must_not_run(pdf):
        raise AssertionError("ikkinchi marta PDF o'qilmasligi kerak")

    monkeypatch.setattr(text_cache, "extract_pages", must_not_run)
    assert get_pages(letter, cache_dir=tmp_path) == first
