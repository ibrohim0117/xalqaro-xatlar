"""src/reading/engines/vision.py — Apple Vision (faqat macOS; to'qilgan rasm bilan)."""

import io
import sys
from pathlib import Path

import pytest

from src.reading.engines import make_reader
from src.reading.engines.vision import group_lines

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
