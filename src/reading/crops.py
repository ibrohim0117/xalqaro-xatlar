"""B5.3b: sahifadan bo'lak kesish (qo'lyozma joyi) — OCR modellariga berish uchun, yuqori aniqlikda.

Koordinatalar nisbiy (0..1, engine/locate bilan bir xil). Diskka yozish — chaqiruvchining ishi
(o'lchov skripti outputs/ ga yozadi; prototip esa bo'lakni faqat xotirada ishlatadi).
"""

import pymupdf

CROP_DPI = 300  # OCR uchun (Tesseract ham shu aniqlikda o'qiydi)
CROP_PAD = 0.01  # qo'lyozma ramkadan biroz chiqib ketishi mumkin — har tomonga sahifaning 1% i


def crop_png(page: pymupdf.Page, box: dict, dpi: int = CROP_DPI, pad: float = CROP_PAD) -> bytes:
    """box ({"x0", "y0", "x1", "y1"}, 0..1) qismini PNG qilib qaytaradi."""
    rect = page.rect
    clip = pymupdf.Rect(
        max(box["x0"] - pad, 0.0) * rect.width,
        max(box["y0"] - pad, 0.0) * rect.height,
        min(box["x1"] + pad, 1.0) * rect.width,
        min(box["y1"] + pad, 1.0) * rect.height,
    )
    return page.get_pixmap(dpi=dpi, clip=clip).tobytes("png")
