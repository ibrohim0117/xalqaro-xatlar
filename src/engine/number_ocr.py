"""B5.5: raqam — sana dvigateli o'qigan o'sha bo'lak matnlaridan (qo'shimcha OCR chaqiruvi yo'q),
matn qatlami va sahifa OCR'idagi "№" raqamidan hamda jo'natuvchining raqam qolipidan.

Qoida — fields/number_vote.number_reading (o'lchov: scripts/ocr/number_failures, NP qatori; dev 70):
qolip bilan 12 tadan 11 to'g'ri "tekshiring" belgisi bilan yoziladi; bir bosishda (yozilgan + 3 ta
taklif) 39/70, avvalgi prototipda 9/70. Sana matn qatlamidan olingan xatlarda OCR ishlamaydi —
raqam faqat matndan (taklif).
"""

from dataclasses import dataclass, field

from src.engine.date_ocr import DateReading
from src.fields.date_number import date_and_number
from src.fields.number_template import Template
from src.fields.number_vote import engine_numbers, number_reading
from src.reading.pages import CachedPage


@dataclass
class NumberReading:
    prefill: str | None = None  # yoziladi, lekin "tekshiring"
    suggestions: list[str] = field(default_factory=list)  # 3 tagacha taklif


def read_number(
    first: CachedPage, date: DateReading | None, template: Template | None
) -> NumberReading:
    """date — sana dvigateli natijasi (uning bo'lak matnlari); template — jo'natuvchi qolipi."""
    text = {
        "matn qatlami": date_and_number(first.text_layer)[1],
        "sahifa OCR": date_and_number(first.ocr)[1] if first.ocr else None,
    }
    texts = date.texts if date else {}
    readers = list(texts)
    found = [engine_numbers(texts[reader]) for reader in readers]
    return NumberReading(*number_reading(readers, found, text, template))


def apply_number(answer: dict, reading: NumberReading) -> None:
    """prefill — yoziladi, "tekshirish kerak" qoladi (raqamni xodim doim ko'radi); takliflar —
    ro'yxat (predict'ning bitta taklifi o'rniga)."""
    if reading.prefill:
        answer["rekvizit_document"]["hujjat_raqami"] = reading.prefill
    if "hujjat_raqami" not in answer["tekshirish_kerak"]:
        answer["tekshirish_kerak"].append("hujjat_raqami")
    if reading.suggestions:
        answer["takliflar"]["hujjat_raqami"] = reading.suggestions
