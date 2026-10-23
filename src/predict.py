"""B4.4, B5.1–B5.3: bitta xat uchun AI javobi — boshqarma, jo'natuvchi, imzo, sana, mazmun.

"Model" — dev xatlardan o'rganilgan qiymatlar: har hudud (va notariat) uchun boshqarmaning to'liq
nomi, eng ko'p uchraydigan qisqacha mazmun va jo'natuvchini topish uchun dev xatlari blankining
so'zlari (blankda fuqaro ismi yo'q; telefon va raqamlar saqlanmaydi) hamda jo'natuvchi nomlari.
U outputs/model.json da (gitignore'da) saqlanadi: nomlarni Claude ko'rmaydi.

Javob shakli — xodim to'ldiradigan json bilan bir xil, ustiga "tekshirish_kerak" ro'yxati.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.baseline import most_common
from src.boshqarma import predict_group
from src.dataset import expected_boshqarma, group_of
from src.date_number import date_number_answer
from src.evaluate import REKVIZIT_FIELDS, normalize
from src.regions import REGIONS, region_of_boshqarma
from src.sender import SENDER_MODE, SENDER_THRESHOLD, Matcher, blank_words, header_text
from src.signer import SIGNER_MIN_Y, SIGNER_PAGES, candidates, choose_signer
from src.text_cache import CachedPage

MODEL_FILE = Path("outputs/model.json")
REGION_NAMES = {region.key: region.name for region in REGIONS}


def template_name(key: str) -> str:
    """O'rganilmagan hudud uchun taxminiy nom: "Buxoro viloyati adliya boshqarmasi"."""
    return f"{REGION_NAMES[key]} adliya boshqarmasi"


@dataclass
class Model:
    names: dict[str, str] = field(default_factory=dict)  # "fargona"/"notariat" -> to'liq nom
    summary: str | None = None
    sender_texts: list[str] = field(default_factory=list)  # dev xatlari blankining so'zlari
    sender_names: list[str] = field(default_factory=list)  # ularning jo'natuvchilari


def sender_part(blanks: list[str], truths: list[dict]) -> tuple[list[str], list[str]]:
    """Jo'natuvchini topish uchun: blanklarning so'zlari va json'dagi nomlar."""
    names = [(t.get("rekvizit_document") or {}).get("hujjat_junatuvchi_tashkilot") for t in truths]
    pairs = [(blank_words(b), name) for b, name in zip(blanks, names, strict=True) if name]
    return [text for text, _ in pairs], [name for _, name in pairs]


def learn_model(truths: list[dict], blanks: list[str] | None = None) -> Model:
    """Faqat DEV xatlaridan: boshqarma nomlari, mazmun va jo'natuvchilar (1-sahifa bilan)."""
    by_key: dict[str, list[str]] = {}
    for truth in truths:
        name = expected_boshqarma(truth)
        key = "notariat" if group_of(name) == "notariat" else region_of_boshqarma(name)
        if key:
            by_key.setdefault(key, []).append(name)
    names = {key: most_common(values)[0] for key, values in by_key.items()}
    summaries = [
        (t.get("rekvizit_document") or {}).get("hujjatning_qisqacha_mazmuni") for t in truths
    ]
    sender_texts, sender_names = sender_part(blanks, truths) if blanks else ([], [])
    return Model(names, most_common(summaries)[0], sender_texts, sender_names)


def template_matches(model: Model) -> tuple[int, int]:
    """O'rganilgan viloyat nomlaridan nechtasi shablonga mos (nomlarni ko'rsatmasdan tekshirish)."""
    keys = [k for k in model.names if k in REGION_NAMES]
    same = sum(normalize(model.names[k]) == normalize(template_name(k)) for k in keys)
    return same, len(keys)


def save_model(model: Model, path: Path = MODEL_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(model), ensure_ascii=False, indent=2), encoding="utf-8")


def load_model(path: Path = MODEL_FILE) -> Model:
    return Model(**json.loads(path.read_text(encoding="utf-8")))


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
    if model.sender_texts:
        matcher = Matcher(model.sender_texts, model.sender_names)
        sender, score = matcher.best(header_text(pages, SENDER_MODE))
        if score >= SENDER_THRESHOLD:
            rekvizit["hujjat_junatuvchi_tashkilot"] = sender
        else:  # notanish jo'natuvchi — taxmin yozilmaydi
            flags.append("hujjat_junatuvchi_tashkilot")
    signer = choose_signer(candidates(pages, SIGNER_PAGES), min_y=SIGNER_MIN_Y)
    if signer:
        rekvizit["imzolagan_shaxs"] = signer.latin()
    else:  # imzo matnda o'qilmagan (qo'lda, shtamp) yoki shakli boshqacha
        flags.append("imzolagan_shaxs")
    # Sana: matn qatlamidan topilsa avtomatik; raqam — doim xodim tekshiradi (faqat taklif)
    rekvizit["hujjat_sana"], suggestions = date_number_answer(pages[0])
    if not rekvizit["hujjat_sana"]:
        flags.append("hujjat_sana")
    flags.append("hujjat_raqami")
    return {
        "rekvizit_document": rekvizit,
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": [name] if name else []}],
        "tekshirish_kerak": flags,
        "takliflar": suggestions,  # AI o'qigan, lekin maydonga yozilmagan qiymatlar
    }
