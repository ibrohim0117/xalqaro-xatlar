"""B7.1–B7.2: bitta yangi PDF uchun to'liq zanjir — PDF -> matn (1–6-sahifa) -> AI javobi.

Skriptlar (B4–B5) matnni keshdan olardi. Bu yerda esa xodim yuklagan yangi PDF keladi:
u baytlar ko'rinishida xotirada qayta ishlanadi, diskka yozilmaydi va keshga tushmaydi.

Model = dev xatlaridan o'rganilgan qiymatlar (outputs/model.json, run_predict yasaydi)
+ xodim tasdiqlagan jo'natuvchilar (outputs/feedback.jsonl).
"""

import time
from dataclasses import dataclass
from pathlib import Path

from src.evaluate import SPACELESS, field_values, normalize
from src.feedback import FEEDBACK_FILE, load_confirmed, with_confirmed
from src.predict import MODEL_FILE, Model, load_model, predict
from src.sender import SENDER_MODE, header_text
from src.text_cache import OcrStats, extract_pages

MAX_PAGES = 6  # asosiy matn 1–2-sahifada, aniqlik uchun 1–6 (rahbar va Ibrohim qarori)


@dataclass
class Result:
    answer: dict  # AI javobi (xodim to'ldiradigan json shaklida)
    blank: str  # /confirm uchun: xodim tasdiqlasa, xotiraga shu blank yoziladi
    pages: int  # nechta sahifa o'qildi
    seconds: float  # umumiy vaqt
    ocr: OcrStats  # shundan OCR'ga ketgani


def current_model(model_file: Path = MODEL_FILE, feedback_file: Path = FEEDBACK_FILE) -> Model:
    """Dev modeli + hozirgacha tasdiqlangan jo'natuvchilar."""
    return with_confirmed(load_model(model_file), *load_confirmed(feedback_file))


def process_pdf(pdf: Path | bytes, model: Model) -> Result:
    start = time.perf_counter()
    stats = OcrStats()
    pages = extract_pages(pdf, max_pages=MAX_PAGES, stats=stats)
    if not pages:
        raise ValueError("PDF'da sahifa yo'q")
    answer = predict(pages, model)
    blank = header_text(pages, SENDER_MODE)
    return Result(answer, blank, len(pages), time.perf_counter() - start, stats)


def _same(a: str | None, b: str | None, field: str) -> bool:
    spaceless = field in SPACELESS
    return bool(a) and normalize(a, spaceless) == normalize(b, spaceless)


def compare(answer: dict, truth: dict) -> dict[str, dict]:
    """Test rejimi: har maydon bo'yicha AI javobi va to'g'ri javob (evaluate.py qoidalari bilan).
    mos: True/False, AI javob bermagan bo'lsa — None ("tekshirish kerak" — xato emas).
    taklif_mos: maydon bo'sh, lekin takliflardan biri to'g'ri bo'lsa — True."""
    suggestions = answer.get("takliflar") or {}
    out = {}
    for field, (predicted, expected) in field_values(answer, truth).items():
        row = {"ai": predicted, "togri": expected, "mos": None}
        if predicted:
            row["mos"] = _same(predicted, expected, field)
        if field in suggestions:
            options = suggestions[field]
            options = options if isinstance(options, list) else [options]
            row["taklif_mos"] = any(_same(o, expected, field) for o in options)
        out[field] = row
    return out
