"""B7.1–B7.2: bitta yangi PDF uchun to'liq zanjir — PDF -> matn (1–6-sahifa) -> AI javobi.

Skriptlar (B4–B5) matnni keshdan olardi. Bu yerda esa xodim yuklagan yangi PDF keladi:
u baytlar ko'rinishida xotirada qayta ishlanadi, diskka yozilmaydi va keshga tushmaydi.

Model = dev xatlaridan o'rganilgan qiymatlar (outputs/model.json, run_predict yasaydi)
+ xodim tasdiqlagan jo'natuvchilar (outputs/feedback.jsonl).
B5.3c: sana dvigateli (date_ocr) berilsa — qo'lyozma sana bo'laklardan o'qiladi.
B5.5: raqam — o'sha bo'lak matnlaridan + matn qatlami + jo'natuvchining raqam qolipi (number_ocr).
B5.15: imzo topilmasa yoki PDF matnida buzilgan bo'lsa — Apple Vision (signer_ocr).
"""

import time
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

from src.engine.date_ocr import DateOcr, DateReading, apply_reading
from src.engine.feedback import FEEDBACK_FILE, load_confirmed, with_confirmed
from src.engine.locate import box, locate
from src.engine.model import MODEL_FILE, Model, load_model, number_template
from src.engine.number_ocr import NumberReading, apply_number, read_number
from src.engine.predict import predict
from src.engine.signer_ocr import VISION, apply_signer, vision_fallback
from src.fields.sender import SENDER_MODE, header_text
from src.reading.pages import OcrStats, extract_pages, open_pdf

MAX_PAGES = 6  # asosiy matn 1–2-sahifada, aniqlik uchun 1–6 (rahbar va Ibrohim qarori)


@dataclass
class Result:
    answer: dict  # AI javobi (xodim to'ldiradigan json shaklida)
    blank: str  # /confirm uchun: xodim tasdiqlasa, xotiraga shu blank yoziladi
    pages: int  # nechta sahifa o'qildi
    seconds: float  # umumiy vaqt
    ocr: OcrStats  # shundan OCR'ga ketgani
    boxes: dict[str, list[dict]]  # maydon -> qayerdan olingani (sahifa va to'rtburchak)
    date: DateReading | None = None  # sana dvigateli natijasi (ishlatilgan bo'lsa)
    number: NumberReading | None = None  # raqam natijasi


def current_model(model_file: Path = MODEL_FILE, feedback_file: Path = FEEDBACK_FILE) -> Model:
    """Dev modeli + hozirgacha tasdiqlangan jo'natuvchilar."""
    return with_confirmed(load_model(model_file), *load_confirmed(feedback_file))


def process_pdf(
    pdf: Path | bytes,
    model: Model,
    date_ocr: DateOcr | None = None,
    received: Date | None = None,
) -> Result:
    """received — xat kelgan sana (sana oynasi uchun); berilmasa — bugun."""
    start = time.perf_counter()
    stats = OcrStats()
    pages = extract_pages(pdf, max_pages=MAX_PAGES, stats=stats)
    if not pages:
        raise ValueError("PDF'da sahifa yo'q")
    answer = predict(pages, model)
    blank = header_text(pages, SENDER_MODE)
    boxes = locate(pages)
    reading = None
    if date_ocr is not None:
        with open_pdf(pdf) as doc:
            reading = date_ocr.read(doc[0], pages[0], received or Date.today())
            if found := vision_fallback(doc[0], pages, date_ocr.reader(VISION)):
                signer, repaired = found
                apply_signer(answer, signer, repaired)
                boxes["imzolagan_shaxs"] = [box(signer.page, *signer.box)]
        apply_reading(answer, reading)
    sender = answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"]
    number = read_number(pages[0], reading, number_template(model, sender))
    apply_number(answer, number)
    seconds = time.perf_counter() - start
    return Result(answer, blank, len(pages), seconds, stats, boxes, reading, number)
