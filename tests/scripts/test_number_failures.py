"""scripts/ocr/number_failures.py testlari — to'qilgan raqamlar bilan."""

import json
import sys
from types import SimpleNamespace

import pytest

from scripts.ocr import number_failures
from scripts.ocr.number_failures import (
    N1,
    N2,
    N3,
    N4,
    N5,
    N6,
    N7,
    N8,
    N9,
    N10,
    READERS,
    digits,
    edit_kinds,
    error_shape,
    relation,
    rules,
)
from src.fields.number_template import Template
from tests.conftest import FAKE_LETTER, make_letter_pdf
from tests.engine.test_date_ocr import NO_PRINTED_DATE
from tests.engine.test_locate import pages_of

TRUTH = "54/07-16606"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("54/07 - 16606", "to'g'ri"),  # bo'shliq — farq emas
        ("54/07-16696", "1 belgi farq"),
        ("54/01-16696", "2-3 belgi farq"),
        ("16606", "qisman"),  # faqat qo'lda yozilgan oxiri o'qilgan
        ("17/08-10/2934", "boshqa raqam"),
        (None, "o'qilmadi"),
    ],
)
def test_relation(value, expected):
    assert relation(value, TRUTH) == expected


def test_edit_kinds():
    assert edit_kinds("54/07-16696", TRUTH) == ["raqam o'rniga raqam"]
    assert edit_kinds("5407-16606", TRUTH) == ["tushib qolgan ajratgich"]
    assert edit_kinds("54/07-166061", TRUTH) == ["ortiqcha raqam"]
    assert edit_kinds("54/07-1б606", TRUTH) == ["harf/raqam almashgan"]
    assert edit_kinds("54/07/16606", TRUTH) == ["ajratgich o'rniga ajratgich"]


def test_error_shape_shows_only_the_shape():
    assert error_shape("54/07-16696", TRUTH) == "99/99-999X9"
    assert error_shape("5407-16606", TRUTH) == "99_99-99999"
    assert error_shape("54/07-166061", TRUTH) == "99/99-99999+"
    assert error_shape("54/07-16606/25", "54/07-16606/2б") == "99/99-99999/9X"  # harf -> A emas, X


def test_digits_only_ignores_format():
    assert digits("54/07 16606") == digits(TRUTH) == "540716606"


def found_with(vlm_extract=None, vlm=None, rapid=None):
    """READERS tartibida OCR'lar raqamlari (vlm-extract, vlm, rapidocr, …)."""
    found = [{} for _ in READERS]
    for name, value in (("vlm-extract", vlm_extract), ("vlm", vlm), ("rapidocr", rapid)):
        if value:
            found[READERS.index(name)] = value
    return found


def test_rules():
    no_text = {"matn qatlami": None, "sahifa OCR": None}
    found = found_with({"header": TRUTH}, vlm={"line": TRUTH})
    written = rules(found, no_text, vlm_date_ok=False)
    assert written[N2] == TRUTH and written[N3] == TRUTH  # eski VLM tasdiqladi
    assert written[N4] is None  # eski VLM'siz tasdiq yo'q
    assert written[N5] is None  # VLM sanasi tasdiqlanmagan
    assert rules(found, no_text, vlm_date_ok=True)[N5] == TRUTH
    assert written[N7] is None  # VLM'ning boshqa ko'rinishi yo'q

    two_views = found_with({"header": TRUTH, "page": "54/07 - 16606"})
    written = rules(two_views, no_text, vlm_date_ok=False)
    assert written[N7] == TRUTH and written[N8] == TRUTH and written[N4] is None

    template = Template("9/9-9", "54/07-")
    other = {"matn qatlami": "17/08-10/2934", "sahifa OCR": None}  # qolipga mos emas
    written = rules(found_with({"header": TRUTH}, rapid={"number": TRUTH}), other, False, template)
    assert written[N9] is None and written[N10] == TRUTH  # matn qatlami chetlandi, N4 qoldi
    good = {"matn qatlami": TRUTH, "sahifa OCR": None}
    assert rules(found_with(), good, False, template)[N10] == TRUTH  # qolipga mos — yoziladi

    printed = {"matn qatlami": "99/01-1", "sahifa OCR": None}
    written = rules(found_with({"header": TRUTH}, rapid={"number": TRUTH}), printed, False)
    assert written[N1] == "99/01-1" and written[N6] == "99/01-1"  # matn qatlami birinchi
    assert written[N4] == TRUTH  # RapidOCR tasdiqladi


def test_main_prints_only_counts(tmp_path, monkeypatch, capsys):
    pages = {  # DOC_1 — sana va raqam bosma; DOC_2 — sana qo'lda (OCR ishlaydi)
        "DOC_1": pages_of(make_letter_pdf(tmp_path / "1.pdf", FAKE_LETTER)),
        "DOC_2": pages_of(make_letter_pdf(tmp_path / "2.pdf", NO_PRINTED_DATE)),
    }
    truth = {"rekvizit_document": {"hujjat_raqami": "55/07-1234", "kirish_sana": "01.04.2026"}}
    extract = {"DOC_2": {"header": '{"sana": "12.03.2026", "raqam": "55/07-1234"}'}}
    other = {"DOC_2": {"line": "12.03.2026 No 55/07-1234"}}
    for reader in READERS:
        saved = extract if reader == "vlm-extract" else other
        (tmp_path / f"{reader}.json").write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(number_failures, "OUT_DIR", tmp_path)
    monkeypatch.setattr(
        number_failures, "list_letters", lambda: [SimpleNamespace(doc_id=d) for d in pages]
    )
    monkeypatch.setattr(number_failures, "load_split", lambda: {"dev": list(pages)})
    monkeypatch.setattr(number_failures, "load_truth", lambda letter: truth)
    monkeypatch.setattr(number_failures, "get_pages", lambda letter: pages[letter.doc_id])
    monkeypatch.setattr(sys, "argv", ["number_failures", "--ids"])

    number_failures.main()
    out = capsys.readouterr().out
    assert "OCR hamma xatda" in out  # B5.12: sanasi bosma DOC_1 da ham OCR ishlaydi
    assert "sanasi bosma (1), eski" in out  # taqqoslash: eski shartda DOC_1 da OCR yo'q
    assert "N6 N1 yoki N3" in out
    assert "55/07" not in out  # ekranga raqam qiymati chiqmaydi
