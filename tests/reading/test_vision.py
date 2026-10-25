"""src/reading/engines/vision.py — Apple Vision (faqat macOS; to'qilgan rasm bilan)."""

import io
import sys
from pathlib import Path

import pytest

from src.fields.signer import find_signer
from src.reading.engines import make_reader
from src.reading.engines.vision import group_lines, to_words
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText

FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")


def test_group_lines_joins_boxes_of_one_line_left_to_right():
    boxes = [
        (0.50, 0.40, 0.10, "55/07-1234"),  # bir qatorda, o'ngda
        (0.52, 0.05, 0.10, "12.03.2026"),  # bir qatorda, chapda (sal pastroq)
        (0.10, 0.05, 0.10, "Исх."),  # yuqoridagi qator
    ]
    assert group_lines(boxes) == ["Исх.", "12.03.2026 55/07-1234"]
    assert group_lines([]) == []


@pytest.mark.skipif(sys.platform != "darwin" or not FONT.exists(), reason="faqat macOS")
def test_vision_reads_a_printed_line():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 160), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 40)
    draw.text((20, 20), "12.03.2026 № 55/07-1234", fill="black", font=font)
    draw.text((20, 90), "Исх. от 05.12.2025 г.", fill="black", font=font)
    png = io.BytesIO()
    image.save(png, "PNG")
    text = make_reader("apple-vision").read(png.getvalue())
    lines = text.splitlines()
    assert "55/07-1234" in lines[0] and "12.03.2026" in lines[0]
    assert "05.12.2025" in lines[1]


def test_to_words_places_words_on_the_page():
    # pastki yarmidagi bo'lak: "Начальник" chapda, "А.Б. Сидоров" o'ngda (alohida bo'laklar)
    found = [(0.40, 0.05, 0.04, 0.20, "Начальник"), (0.40, 0.60, 0.04, 0.30, "А.Б. Сидоров")]
    words = to_words(found, region=(0.0, 0.5, 1.0, 1.0))
    assert [w.text for w in words] == ["Начальник", "А.Б.", "Сидоров"]
    initials = words[1]
    assert initials.y0 == pytest.approx(0.70) and initials.x0 == pytest.approx(0.60)
    assert words[2].x0 > initials.x1 > initials.x0 and words[1].line == words[2].line
    page = CachedPage(1, PageText(1, "ocr", words), None)
    assert find_signer([page]).latin() == "A.B.Sidorov"  # o'sha imzo qoidasi ishlaydi
