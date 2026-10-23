"""Muhit tekshiruvi: butun zanjir sun'iy (to'qilgan) xat bilan ishlaydimi.

reportlab: ruscha xat -> PDF -> PyMuPDF: rasm -> OpenCV: oq-qora -> Tesseract (rus): matn.
Real xatlar ishlatilmaydi. Ishga tushirish: poetry run python -m scripts.data.check_env
"""

import time
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytesseract
from rapidfuzz import fuzz
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

TESSDATA = Path("models/tessdata").resolve()
FONT = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
PDF_PATH = Path("outputs/check_env.pdf")  # vaqtinchalik fayl, gitga kirmaydi

# To'qilgan xat (haqiqiy shaxs va tashkilotlarga aloqasi yo'q)
LINES = [
    "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ",
    "РОССИЙСКОЙ ФЕДЕРАЦИИ ПО ОМСКОЙ ОБЛАСТИ",
    "12.03.2026 № 55/07-1234",
    "Запрос о правовой помощи",
    "В соответствии с Конвенцией о правовой помощи 2002 года просим",
    "направить справку о рождении Иванова Петра Сергеевича,",
    "регистрация произведена отделом ЗАГС Ахунбабаевского района",
    "Ферганской области Узбекской ССР.",
    "Начальник управления                    А.Б. Сидоров",
]


def make_pdf() -> None:
    pdfmetrics.registerFont(TTFont("TNR", FONT))
    c = canvas.Canvas(str(PDF_PATH), pagesize=A4)
    c.setFont("TNR", 13)
    y = 780
    for line in LINES:
        c.drawString(60, y, line)
        y -= 28
    c.save()


def pdf_to_image(path: Path, dpi: int = 300) -> np.ndarray:
    page = pymupdf.open(path)[0]
    print(f"   matn qatlami bormi: {'ha' if page.get_text().strip() else 'yo`q (skaner)'}")
    pix = page.get_pixmap(dpi=dpi)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def main() -> None:
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    make_pdf()
    print(f"1) Sun'iy PDF yasaldi: {PDF_PATH}")

    gray = pdf_to_image(PDF_PATH)
    print(f"2) PDF -> rasm: {gray.shape[1]}x{gray.shape[0]} piksel (300 dpi)")

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    print("3) OpenCV: oq-qora qilindi")

    t0 = time.perf_counter()
    text = pytesseract.image_to_string(binary, lang="rus", config=f'--tessdata-dir "{TESSDATA}"')
    print(f"4) Tesseract (rus): {time.perf_counter() - t0:.1f} s")

    expected = "\n".join(LINES)
    got = "\n".join(line for line in text.splitlines() if line.strip())
    print(f"\n5) O'qilgan matn:\n{got}\n")
    print(f"6) Kutilgan matn bilan o'xshashlik: {fuzz.ratio(expected, got):.1f}%")


if __name__ == "__main__":
    main()
