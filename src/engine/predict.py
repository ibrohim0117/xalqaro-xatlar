"""B4.4, B5.1–B5.3: bitta xat uchun AI javobi — boshqarma, jo'natuvchi, imzo, sana, mazmun.

Javob shakli — xodim to'ldiradigan json bilan bir xil, ustiga "tekshirish_kerak" ro'yxati va
"takliflar". Model (o'rganilgan qiymatlar) — src/engine/model.py.
"""

from src.common.schema import REKVIZIT_FIELDS
from src.engine.model import Model, template_name
from src.fields.boshqarma import predict_group
from src.fields.date_number import date_number_answer
from src.fields.sender import SENDER_MODE, SENDER_THRESHOLD, Matcher, header_text
from src.fields.sender_variants import page_variants
from src.fields.signer import find_signer
from src.reading.pages import CachedPage


def predict(pages: list[CachedPage], model: Model) -> dict:
    """Bitta xat uchun javob (json). Boshqarma topilmasa — bo'sh va "tekshirish kerak"."""
    group, region = predict_group(pages)
    flags = []
    if group == "notariat":
        name = model.names.get("notariat")
    elif group == "viloyat":
        name = model.names.get(region)
        if name is None:  # dev'da bu hudud uchragan emas — nom taxminiy
            name = template_name(region)
            flags.append("boshqarma")
    else:
        name = None
    if name is None:
        flags.append("boshqarma")
    rekvizit = dict.fromkeys(REKVIZIT_FIELDS)
    rekvizit["hujjatning_qisqacha_mazmuni"] = model.summary
    suggestions: dict = {}  # AI o'qigan/tarjima qilgan, lekin maydonga yozilmagan qiymatlar
    sender, score = (
        Matcher(model.sender_texts, model.sender_names).best(header_text(pages, SENDER_MODE))
        if model.sender_texts
        else (None, 0.0)
    )
    if sender and score >= SENDER_THRESHOLD:
        rekvizit["hujjat_junatuvchi_tashkilot"] = sender
    else:  # notanish: taxmin yozilmaydi, xodimga o'zbekcha nom variantlari taklif qilinadi
        flags.append("hujjat_junatuvchi_tashkilot")
        if variants := page_variants(pages):
            suggestions["hujjat_junatuvchi_tashkilot"] = variants
    signer = find_signer(pages)
    if signer:
        rekvizit["imzolagan_shaxs"] = signer.latin()
    else:  # imzo matnda o'qilmagan (qo'lda, shtamp) yoki shakli boshqacha
        flags.append("imzolagan_shaxs")
    # Sana: matn qatlamidan topilsa avtomatik; raqam — doim xodim tekshiradi (faqat taklif)
    rekvizit["hujjat_sana"], date_suggestions = date_number_answer(pages[0])
    suggestions.update(date_suggestions)
    if not rekvizit["hujjat_sana"]:
        flags.append("hujjat_sana")
    flags.append("hujjat_raqami")
    return {
        "rekvizit_document": rekvizit,
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": [name] if name else []}],
        "tekshirish_kerak": flags,
        "takliflar": suggestions,
    }
