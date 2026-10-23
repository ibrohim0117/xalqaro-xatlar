"""B3.4: xat matnini bir marta olib, faylga saqlash (kesh).

OCR sekin (~2.2 s/sahifa), B4–B5 esa kodni ko'p marta ishga tushiradi. Shuning uchun har xat
matni bir marta olinadi va outputs/text_cache/<DOC_id>.json ga yoziladi.
MAXFIYLIK: keshda real xat matni bor — gitignore'da, Claude ochmaydi.

Nima saqlanadi (B3.3 va B3.5 xulosalari bo'yicha):
- hamma sahifa: matn qatlami (bir zumda);
- 1-sahifa: OCR ham — "№" langarini OCR yaxshiroq topadi (80% ga qarshi 65%);
- matn qatlami yo'q sahifalar: OCR;
- eng yaxshi matn sifati 0.7 dan past sahifalar: rus+uzb bilan qayta OCR (lotin yozuvidagi
  FHDYO guvohnomalari va h.k.; dev'da matn qatlami sahifalarining 15% i 0.6 dan past).
"""

import json
from dataclasses import astuple, dataclass
from pathlib import Path

import pymupdf

from src.dataset import Letter
from src.pdf_text import PageText, Word, has_text_layer, ocr_page, text_layer_words, text_quality

CACHE_DIR = Path("outputs/text_cache")
CACHE_VERSION = 3  # OCR sozlamalari o'zgarsa oshiriladi — eski kesh fayllari qayta yasaladi
QUALITY_MIN = 0.7  # eng yaxshi matn sifati shundan past bo'lsa — rus+uzb bilan qayta OCR
LATIN_LANG = "rus+uzb"  # o'zbek lotin yozuvini ham o'qiydi
MAIN_MARGIN = 0.02  # OCR shunchalik tozaroq bo'lsagina matn qatlami o'rniga olinadi
RETRY_MIN_WORDS = 10  # bo'sh yoki deyarli bo'sh sahifa qayta o'qilmaydi


@dataclass
class CachedPage:
    number: int
    text_layer: PageText
    ocr: PageText | None  # 1-sahifa, matn qatlami yo'q yoki sifati past sahifalar uchun

    @property
    def main(self) -> PageText:
        """Asosiy matn: matn qatlami va OCR'dan tozarog'i. Teng bo'lsa — matn qatlami."""
        if self.ocr is None:
            return self.text_layer
        if not has_text_layer(self.text_layer.words):
            return self.ocr
        if text_quality(self.ocr.words) > text_quality(self.text_layer.words) + MAIN_MARGIN:
            return self.ocr
        return self.text_layer


def extract_pages(pdf: Path | bytes, max_pages: int | None = None) -> list[CachedPage]:
    """PDF'dan sahifalarni o'qiydi: matn qatlami har doim, OCR faqat kerakli sahifalarda.
    pdf — fayl yo'li yoki baytlar (API: yuklangan PDF diskka yozilmaydi, xotiradan ochiladi).
    max_pages — faqat dastlabki N sahifa (None — hammasi, kesh uchun)."""
    pages = []
    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    with doc:
        for i, page in enumerate(doc):
            number = i + 1
            if max_pages is not None and number > max_pages:
                break
            words = text_layer_words(page)
            need_ocr = number == 1 or not has_text_layer(words)
            ocr = ocr_page(page, number) if need_ocr else None
            cached = CachedPage(number, PageText(number, "text_layer", words), ocr)
            main = cached.main
            if len(main.words) >= RETRY_MIN_WORDS and text_quality(main.words) < QUALITY_MIN:
                latin = ocr_page(page, number, lang=LATIN_LANG)
                if ocr is None or text_quality(latin.words) > text_quality(ocr.words):
                    cached.ocr = latin
            pages.append(cached)
    return pages


def _dump(page: PageText | None) -> list[list] | None:
    """So'zlar ixcham ro'yxat bo'lib yoziladi: [matn, x0, y0, x1, y1, qator, ishonch]."""
    return None if page is None else [list(astuple(word)) for word in page.words]


def _restore(number: int, source: str, rows: list[list] | None) -> PageText | None:
    return None if rows is None else PageText(number, source, [Word(*row) for row in rows])


def save(pages: list[CachedPage], path: Path) -> None:
    data = {
        "version": CACHE_VERSION,
        "pages": [
            {"number": p.number, "text_layer": _dump(p.text_layer), "ocr": _dump(p.ocr)}
            for p in pages
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # Avval vaqtinchalik faylga, keyin bir harakatda nomini almashtiramiz: yozish o'rtasida
    # to'xtatilsa (Ctrl+C), yarim yozilgan fayl qolmaydi
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load(path: Path) -> list[CachedPage] | None:
    """Keshdan o'qiydi. Fayl yo'q, buzuq yoki versiyasi eski bo'lsa — None (qayta yasash kerak)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("version") != CACHE_VERSION:
        return None
    return [
        CachedPage(
            p["number"],
            _restore(p["number"], "text_layer", p["text_layer"]),
            _restore(p["number"], "ocr", p["ocr"]),
        )
        for p in data["pages"]
    ]


def get_pages(letter: Letter, cache_dir: Path = CACHE_DIR) -> list[CachedPage]:
    """Xat sahifalari: keshda bo'lsa keshdan (bir zumda), bo'lmasa PDF'dan olib keshga yozadi."""
    path = cache_dir / f"{letter.doc_id}.json"
    pages = load(path)
    if pages is None:
        pages = extract_pages(letter.pdf)
        save(pages, path)
    return pages
