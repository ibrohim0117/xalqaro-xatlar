"""src/reading/engines testlari — soxta xatdan kesilgan bosma qator bilan."""

import pymupdf
import pytest

from src.fields.date_number import parse_date, parse_number
from src.reading.crops import crop_png
from src.reading.engines import READERS, make_reader
from tests.conftest import needs_tesseract

LINE = {"x0": 0.07, "y0": 0.115, "x1": 0.45, "y1": 0.135}  # "12.03.2026 № 55/07-1234" (conftest)


@needs_tesseract
@pytest.mark.parametrize("name", [n for n in READERS if n.startswith("tesseract")])
def test_tesseract_reads_printed_line(letter_pdf, name):
    with pymupdf.open(letter_pdf) as doc:
        png = crop_png(doc[0], LINE)
    reader = make_reader(name)
    text = reader.read(png)
    assert reader.name == name
    assert parse_date(text) == "12.03.2026"
    assert parse_number(text) == "55/07-1234"
