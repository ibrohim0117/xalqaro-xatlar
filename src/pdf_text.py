"""B3: PDF sahifasidan so'zlar va ularning sahifadagi joyi.

Joy nisbiy: chap-yuqori burchak (0, 0), o'ng-past burchak (1, 1). Shunda matn qatlami
(punktlarda) va OCR (piksellarda) natijalari bir xil o'lchovda bo'ladi.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import pytesseract

# Til paketlari loyiha ichida (oflayn): models/tessdata
TESSDATA = Path(__file__).resolve().parents[1] / "models" / "tessdata"
TESS_CONFIG = f'--tessdata-dir "{TESSDATA}"'
TEXT_LAYER_MIN_CHARS = 50  # sahifada shundan kam belgi bo'lsa — matn qatlami yo'q deb hisoblanadi


@dataclass(frozen=True)
class Word:
    text: str
    x0: float  # chap cheti
    y0: float  # yuqori cheti
    x1: float  # o'ng cheti
    y1: float  # pastki cheti
    line: int  # sahifadagi qator raqami (0 dan)
    conf: float | None = None  # OCR ishonchi (0..100); matn qatlamida None


@dataclass
class PageText:
    number: int  # sahifa raqami, 1 dan
    source: str  # "text_layer" yoki "ocr"
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        """So'zlarni qatorlarga yig'ib, oddiy matnga aylantiradi."""
        lines: dict[int, list[str]] = {}
        for word in self.words:
            lines.setdefault(word.line, []).append(word.text)
        return "\n".join(" ".join(words) for words in lines.values())


def text_layer_words(page: pymupdf.Page) -> list[Word]:
    """PDF ichidagi tayyor matn qatlamidan so'zlar (OCR'siz, bir zumda)."""
    width, height = page.rect.width, page.rect.height
    line_ids: dict[tuple[int, int], int] = {}
    words = []
    for x0, y0, x1, y1, text, block, line, _ in page.get_text("words"):
        # PyMuPDF qatorni (blok, qator) juftligi bilan beradi — sahifa bo'yicha bitta raqamga
        line_id = line_ids.setdefault((block, line), len(line_ids))
        words.append(Word(text, x0 / width, y0 / height, x1 / width, y1 / height, line_id))
    return words


def read_text_layer(pdf: Path, max_pages: int | None = None) -> list[PageText]:
    """Har sahifa uchun matn qatlamidagi so'zlar. Skaner sahifada ro'yxat bo'sh bo'ladi."""
    with pymupdf.open(pdf) as doc:
        pages = list(doc)[:max_pages]
        return [PageText(i + 1, "text_layer", text_layer_words(p)) for i, p in enumerate(pages)]


# ── OCR: matn qatlami yo'q sahifalar uchun ──


def page_image(page: pymupdf.Page, dpi: int = 300) -> np.ndarray:
    """Sahifani kulrang rasmga aylantiradi (OpenCV ishlaydigan numpy massiv)."""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def binarize(gray: np.ndarray) -> np.ndarray:
    """Oq-qora qiladi. Har bir kichik bo'lak (31x31 piksel) o'z yorug'ligiga qarab hal qilinadi,
    shuning uchun soyali yoki notekis yoritilgan skanerda ham harflar aniq chiqadi."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def ocr_words(image: np.ndarray, lang: str = "rus") -> list[Word]:
    """Tesseract bilan so'zlar: matni, joyi (pikseldan nisbiyga o'tkazilgan) va ishonchi."""
    height, width = image.shape[:2]
    data = pytesseract.image_to_data(
        image, lang=lang, config=TESS_CONFIG, output_type=pytesseract.Output.DICT
    )
    line_ids: dict[tuple[int, int, int], int] = {}
    words = []
    for i, text in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if conf < 0 or not text.strip():  # -1 — so'z emas (blok, qator sarlavhasi)
            continue
        # Tesseract qatorni (blok, paragraf, qator) uchligi bilan beradi
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line_id = line_ids.setdefault(key, len(line_ids))
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(
            Word(text, x / width, y / height, (x + w) / width, (y + h) / height, line_id, conf)
        )
    return words


def ocr_page(page: pymupdf.Page, number: int, lang: str = "rus") -> PageText:
    return PageText(number, "ocr", ocr_words(binarize(page_image(page)), lang))


def read_ocr(pdf: Path, max_pages: int | None = None) -> list[PageText]:
    """Matn qatlamiga qaramasdan hamma sahifani OCR qiladi (solishtirish uchun)."""
    with pymupdf.open(pdf) as doc:
        return [ocr_page(p, i + 1) for i, p in enumerate(list(doc)[:max_pages])]


# ── Asosiy kirish nuqtasi ──


def has_text_layer(words: list[Word]) -> bool:
    return sum(len(word.text) for word in words) >= TEXT_LAYER_MIN_CHARS


# "Toza" so'z: faqat kirill yoki faqat lotin harflari (o'zbekcha o', g' bilan) va tinish belgilari
CLEAN_WORD = re.compile(r"^[«(\"']?(?:[А-Яа-яЁёЎўҚқҒғҲҳ-]+|[A-Za-z'ʻ’`-]+)[.,;:!?)»\"']*$")
HAS_LETTER = re.compile(r"[А-Яа-яЁёЎўҚқҒғҲҳA-Za-z]")


MIN_LETTERS = 3  # "Ш", "ии" kabi bo'laklar bahoni ko'tarmasin
OCR_CONF_MIN = 60  # OCR so'zi shundan past ishonch bilan o'qilgan bo'lsa — toza emas


def is_clean(word: Word) -> bool:
    """Faqat kirill yoki faqat lotin harflari; OCR'da esa ishonchi ham yetarli bo'lishi kerak.
    Ma'nosiz OCR so'zlari ("SJCQJBO") ham harflardan iborat — ularni past ishonch ajratadi."""
    sure = word.conf is None or word.conf >= OCR_CONF_MIN
    return sure and bool(CLEAN_WORD.match(word.text))


def text_quality(words: list[Word]) -> float:
    """Kamida 3 harfli so'zlarning qanchasi "toza" (0..1). Oddiy matnda yuqori, axlatda past.
    Raqamlar (sana, telefon) hisobga olinmaydi — ularda harf yo'q."""
    lettered = [w for w in words if len(HAS_LETTER.findall(w.text)) >= MIN_LETTERS]
    if not lettered:
        return 0.0
    return sum(is_clean(w) for w in lettered) / len(lettered)


def read_pdf(pdf: Path, max_pages: int | None = None) -> list[PageText]:
    """Har sahifa uchun alohida: matn qatlami bo'lsa — o'sha (tez), bo'lmasa — OCR."""
    result = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(list(doc)[:max_pages]):
            words = text_layer_words(page)
            if has_text_layer(words):
                result.append(PageText(i + 1, "text_layer", words))
            else:
                result.append(ocr_page(page, i + 1))
    return result
