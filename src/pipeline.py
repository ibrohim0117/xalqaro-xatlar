"""B7.1: bitta yangi PDF uchun to'liq zanjir — PDF -> matn (1–6-sahifa) -> AI javobi.

Skriptlar (B4–B5) matnni keshdan olardi. Bu yerda esa xodim yuklagan yangi PDF keladi:
u baytlar ko'rinishida xotirada qayta ishlanadi, diskka yozilmaydi va keshga tushmaydi.

Model = dev xatlaridan o'rganilgan qiymatlar (outputs/model.json, run_predict yasaydi)
+ xodim tasdiqlagan jo'natuvchilar (outputs/feedback.jsonl).
"""

from pathlib import Path

from src.feedback import FEEDBACK_FILE, load_confirmed, with_confirmed
from src.predict import MODEL_FILE, Model, load_model, predict
from src.sender import SENDER_MODE, header_text
from src.text_cache import extract_pages

MAX_PAGES = 6  # asosiy matn 1–2-sahifada, aniqlik uchun 1–6 (rahbar va Ibrohim qarori)


def current_model(model_file: Path = MODEL_FILE, feedback_file: Path = FEEDBACK_FILE) -> Model:
    """Dev modeli + hozirgacha tasdiqlangan jo'natuvchilar."""
    return with_confirmed(load_model(model_file), *load_confirmed(feedback_file))


def process_pdf(pdf: Path | bytes, model: Model) -> tuple[dict, str]:
    """(AI javobi, blank matni). Blank matni /confirm uchun kerak: xodim jo'natuvchi nomini
    tasdiqlaganda xotiraga aynan shu blank yoziladi (u yerda faqat 3+ harfli so'zlar qoladi)."""
    pages = extract_pages(pdf, max_pages=MAX_PAGES)
    if not pages:
        raise ValueError("PDF'da sahifa yo'q")
    return predict(pages, model), header_text(pages, SENDER_MODE)
