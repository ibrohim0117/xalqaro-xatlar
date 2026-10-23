"""src/engine/locate.py testlari — soxta xat (conftest) bilan, OCR'siz."""

import pymupdf
import pytest

from src.engine.locate import locate, ocr_regions, reply_box
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, text_layer_words
from tests.conftest import FAKE_LETTER, make_letter_pdf

A4_WIDTH, A4_HEIGHT = 595, 842


def pages_of(path) -> list[CachedPage]:
    with pymupdf.open(path) as doc:
        return [
            CachedPage(i + 1, PageText(i + 1, "text_layer", text_layer_words(page)), None)
            for i, page in enumerate(doc)
        ]


@pytest.fixture
def boxes(tmp_path):
    return locate(pages_of(make_letter_pdf(tmp_path / "xat.pdf")))


def inside(box: dict, x: float, y: float) -> bool:
    """(x, y) punktdagi nuqta to'rtburchak ichidami (y — yozuv tagi, shuning uchun biroz yuqori)."""
    return box["x0"] <= x / A4_WIDTH <= box["x1"] and box["y0"] <= (y - 4) / A4_HEIGHT <= box["y1"]


def test_every_field_points_to_its_line(boxes):
    assert inside(boxes["hujjat_junatuvchi_tashkilot"][0], 60, 60)  # "УПРАВЛЕНИЕ ЮСТИЦИИ"
    assert inside(boxes["hujjat_sana"][0], 60, 110)  # "12.03.2026 № …" — "№" dan chapi
    assert inside(boxes["hujjat_raqami"][0], 160, 110)  # "№" dan o'ngi
    assert inside(boxes["imzolagan_shaxs"][0], 420, 700)  # "А.Б. Сидоров"
    assert inside(boxes["boshqarma"][0], 300, 216)  # "… Ферганская область."
    assert all(b["sahifa"] == 1 for field in boxes.values() for b in field)


def test_sender_block_stops_above_number_line(boxes):
    assert boxes["hujjat_junatuvchi_tashkilot"][0]["y1"] < boxes["hujjat_sana"][0]["y0"]


def test_handwriting_space_is_kept_after_anchor(tmp_path):
    # Raqam qo'lda yozilgan: bosma qatorda faqat "№" bor — ramka baribir o'ngga kengayadi
    letter = [line for line in FAKE_LETTER if "№" not in line[2]] + [(50, 110, "№")]
    boxes = locate(pages_of(make_letter_pdf(tmp_path / "xat.pdf", letter)))
    number = boxes["hujjat_raqami"][0]
    assert number["x1"] - number["x0"] >= 0.2


def test_unknown_region_and_signer_have_no_box(tmp_path):
    letter = [line for line in FAKE_LETTER if "Ферган" not in line[2] and "Сидоров" not in line[2]]
    boxes = locate(pages_of(make_letter_pdf(tmp_path / "xat.pdf", letter)))
    assert "boshqarma" not in boxes and "imzolagan_shaxs" not in boxes


def test_reply_line_box(tmp_path):
    letter = [*FAKE_LETTER, (50, 130, "На № ___ от ___")]  # javob xat qatori (qo'lda to'ldiriladi)
    reply = reply_box(pages_of(make_letter_pdf(tmp_path / "xat.pdf", letter))[0])
    assert inside(reply, 75, 130)  # "№" va undan o'ngdagi joy
    assert reply["x1"] - reply["x0"] >= 0.45
    assert reply_box(pages_of(make_letter_pdf(tmp_path / "oddiy.pdf"))[0]) is None


def test_regions_of_a_letter(tmp_path):
    first = pages_of(make_letter_pdf(tmp_path / "xat.pdf"))[0]
    found = ocr_regions(first)
    assert set(found) == {"header", "line", "date", "number"}  # "На №" qatori yo'q
    assert (
        found["line"]["x0"] == found["date"]["x0"] and found["line"]["x1"] == found["number"]["x1"]
    )


def test_without_anchor_only_header_is_cut(tmp_path):
    letter = [line for line in FAKE_LETTER if "№" not in line[2]]
    assert set(ocr_regions(pages_of(make_letter_pdf(tmp_path / "xat.pdf", letter))[0])) == {
        "header"
    }
