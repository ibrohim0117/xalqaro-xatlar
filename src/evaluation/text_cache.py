"""B3.4: real xat matnini bir marta olib, faylga saqlash (kesh) — faqat o'lchov skriptlari uchun.

OCR sekin (~2.2 s/sahifa), B4–B5 esa kodni ko'p marta ishga tushiradi. Shuning uchun har xat
matni bir marta olinadi (src/reading/pages.py qoidalari bilan) va outputs/text_cache/<DOC_id>.json
ga yoziladi. Prototip (API) keshni ishlatmaydi.
MAXFIYLIK: keshda real xat matni bor — gitignore'da, Claude ochmaydi.
"""

import json
from dataclasses import astuple
from pathlib import Path

from src.evaluation.dataset import Letter
from src.reading.pages import CachedPage, extract_pages
from src.reading.pdf_text import PageText, Word

CACHE_DIR = Path("outputs/text_cache")
# reading/pages.py dagi OCR sozlamalari o'zgarsa oshiriladi — eski kesh fayllari qayta yasaladi
CACHE_VERSION = 3


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
