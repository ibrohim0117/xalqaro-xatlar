"""B3: PDF sahifasidan so'zlar va ularning sahifadagi joyi.

Joy nisbiy: chap-yuqori burchak (0, 0), o'ng-past burchak (1, 1). Shunda matn qatlami
(punktlarda) va OCR (piksellarda) natijalari bir xil o'lchovda bo'ladi.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


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
