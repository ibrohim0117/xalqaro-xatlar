"""B4.4, B5.1–B5.3: bitta xat uchun AI javobi — boshqarma, jo'natuvchi, imzo, sana, mazmun.

Javob shakli — xodim to'ldiradigan json bilan bir xil, ustiga "tekshirish_kerak" ro'yxati va
"takliflar". Model (o'rganilgan qiymatlar) — src/engine/model.py.
"""

from src.common.schema import REKVIZIT_FIELDS
from src.engine.model import Model, template_name
from src.fields.boshqarma import predict_group
from src.fields.date_number import date_number_answer
from src.fields.reply import our_reference, own_numbers, reply_summary
from src.fields.sender import (
    SENDER_MARGIN,
    SENDER_MODE,
    SENDER_THRESHOLD,
    Matcher,
    header_text,
)
from src.fields.sender_variants import blank_places, page_variants, same_place
from src.fields.signer import find_signer
from src.reading.pages import CachedPage

KNOWN_SUGGESTIONS = 3  # past balli jo'natuvchida taklif qilinadigan tanish tashkilotlar
REPLY_PAGES = 6  # javob xat havolasi shu sahifalardan qidiriladi (pipeline.MAX_PAGES bilan bir xil)


def predict(pages: list[CachedPage], model: Model) -> dict:
    """Bitta xat uchun javob (json). Boshqarma topilmasa — bo'sh va "tekshirish kerak"."""
    group, region = predict_group(pages)
    flags = []
    if group == "notariat":
        name = model.names.get("notariat")
    elif group == "xalqaro":
        name = model.names.get("xalqaro")
        if name:  # qoida faqat 2 ta dev misolga tayanadi — doim "tekshiring"
            flags.append("boshqarma")
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
    # B5.6: javob xat — matnda bizning oldingi xatimiz raqami (vazirlik shaklida) va sanasi bor
    shapes = set(model.reply_shapes)
    if reference := our_reference(pages[:REPLY_PAGES], own_numbers(pages[0]), shapes):
        rekvizit["hujjatning_qisqacha_mazmuni"] = reply_summary(*reference)
    suggestions: dict = {}  # AI o'qigan/tarjima qilgan, lekin maydonga yozilmagan qiymatlar
    ranking = (
        Matcher(model.sender_texts, model.sender_names).ranked(header_text(pages, SENDER_MODE))
        if model.sender_texts
        else []
    )
    score, sender = ranking[0] if ranking else (0.0, None)
    margin = score - (ranking[1][0] if len(ranking) > 1 else 0.0)
    if sender and score >= SENDER_THRESHOLD:
        rekvizit["hujjat_junatuvchi_tashkilot"] = sender
    elif sender and margin >= SENDER_MARGIN and same_place(blank_places(pages), sender):
        # B5.8: aniq ustun va blankdagi joy mos, lekin ball past — yoziladi, "tekshiring" bilan
        rekvizit["hujjat_junatuvchi_tashkilot"] = sender
        flags.append("hujjat_junatuvchi_tashkilot")
    else:  # notanish yoki ball past: taxmin yozilmaydi, xodimga takliflar
        flags.append("hujjat_junatuvchi_tashkilot")
        # o'zbekcha nom variantlari (blankdan) va B5.10: eng o'xshash TANISH tashkilotlar — ball
        # past bo'lsa ham to'g'risi ko'pincha shular orasida (dev: 2 xatda 1- va 2-o'rinda)
        known = [name for score, name in ranking[:KNOWN_SUGGESTIONS] if score > 0]
        if options := list(dict.fromkeys(page_variants(pages) + known)):
            suggestions["hujjat_junatuvchi_tashkilot"] = options
    signer = find_signer(pages)
    if signer:
        rekvizit["imzolagan_shaxs"] = signer.latin()
        if signer.damaged:  # birinchi bosh harf PDF matnida yo'qolgan bo'lishi mumkin
            flags.append("imzolagan_shaxs")
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
