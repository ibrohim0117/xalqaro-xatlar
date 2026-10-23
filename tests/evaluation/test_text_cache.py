"""src/evaluation/text_cache.py testlari — soxta xatlar bilan, kesh vaqtinchalik papkada."""

import json

from src.evaluation import text_cache
from src.evaluation.dataset import Letter
from src.evaluation.text_cache import get_pages, load, save
from src.reading.pages import extract_pages
from tests.conftest import needs_tesseract


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
