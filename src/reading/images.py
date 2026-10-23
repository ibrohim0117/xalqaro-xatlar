"""B7.3: sahifalar rasmi — faqat xodimga ko'rsatish uchun. Xotirada yasaladi, diskka yozilmaydi."""

import base64

from src.reading.pages import open_pdf

VIEW_DPI = 120  # ekranda o'qishga yetarli (A4 ~ 990 x 1400 px), javob hajmi kichik
JPEG_QUALITY = 80


def page_images(pdf: bytes, max_pages: int, dpi: int = VIEW_DPI) -> list[str]:
    """Dastlabki sahifalar JPEG ko'rinishida, data URI — brauzer uni <img> ga to'g'ridan-to'g'ri
    qo'yadi."""
    with open_pdf(pdf) as doc:
        return [
            "data:image/jpeg;base64,"
            + base64.b64encode(
                page.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=JPEG_QUALITY)
            ).decode()
            for page in doc.pages(0, min(max_pages, doc.page_count))
        ]
