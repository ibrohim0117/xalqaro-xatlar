"""Model — dev xatlardan o'rganilgan qiymatlar: har hudud (va notariat) uchun boshqarmaning to'liq
nomi, eng ko'p uchraydigan qisqacha mazmun va jo'natuvchini topish uchun dev xatlari blankining
so'zlari (blankda fuqaro ismi yo'q; telefon va raqamlar saqlanmaydi) hamda jo'natuvchi nomlari,
har jo'natuvchining raqam qolipi (B5.5: tuzilish va doimiy bosh qism "54/07-", tartib raqamisiz),
bizning raqamlarimiz shakllari (B5.6: javob xatlarni tanish uchun, "99/99-9/9999" — qiymat emas).
U outputs/model.json da (gitignore'da) saqlanadi: nomlarni Claude ko'rmaydi.
"""

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.common.text import most_common, normalize
from src.fields.number_template import Template, learn, shape
from src.fields.regions import REGIONS, region_of_boshqarma
from src.fields.reply import parse_reply_summary
from src.fields.sender import blank_words

MODEL_FILE = Path("outputs/model.json")
REGION_NAMES = {region.key: region.name for region in REGIONS}


def template_name(key: str) -> str:
    """O'rganilmagan hudud uchun taxminiy nom: "Buxoro viloyati adliya boshqarmasi".
    B5.7 da nom shaklini boshqa nomlardan o'rganish sinaldi — LOO 0/10 (bu shablon 5/12):
    json'dagi nomlar hududdan hududga har xil yozilgan, umumiy shakl yo'q — qaytarildi."""
    return f"{REGION_NAMES[key]} adliya boshqarmasi"


@dataclass
class Model:
    names: dict[str, str] = field(default_factory=dict)  # "fargona"/"notariat" -> to'liq nom
    summary: str | None = None
    sender_texts: list[str] = field(default_factory=list)  # dev xatlari blankining so'zlari
    sender_names: list[str] = field(default_factory=list)  # ularning jo'natuvchilari
    # jo'natuvchi (normalize) -> raqam qolipi {"structure": "9/9-9/9", "prefix": "54/07-"}
    number_templates: dict[str, dict] = field(default_factory=dict)
    reply_shapes: list[str] = field(default_factory=list)  # bizning raqamlar shakli (javob xatlar)


def sender_part(blanks: list[str], truths: list[dict]) -> tuple[list[str], list[str]]:
    """Jo'natuvchini topish uchun: blanklarning so'zlari va json'dagi nomlar."""
    names = [(t.get("rekvizit_document") or {}).get("hujjat_junatuvchi_tashkilot") for t in truths]
    pairs = [(blank_words(b), name) for b, name in zip(blanks, names, strict=True) if name]
    return [text for text, _ in pairs], [name for _, name in pairs]


def number_part(truths: list[dict]) -> dict[str, dict]:
    """Har jo'natuvchining raqam qolipi — uning kamida 2 ta xatidan (number_template.learn)."""
    by_sender: dict[str, list[str]] = {}
    for truth in truths:
        doc = truth.get("rekvizit_document") or {}
        sender, number = doc.get("hujjat_junatuvchi_tashkilot"), doc.get("hujjat_raqami")
        if sender and number:
            by_sender.setdefault(normalize(sender), []).append(number)
    learned = {sender: learn(numbers) for sender, numbers in by_sender.items()}
    return {sender: asdict(template) for sender, template in learned.items() if template}


def reply_part(truths: list[dict]) -> list[str]:
    """Javob xatlar mazmunidagi (bizning oldingi xatimiz) raqamlarning shakllari."""
    docs = [t.get("rekvizit_document") or {} for t in truths]
    summaries = [doc.get("hujjatning_qisqacha_mazmuni") for doc in docs]
    return sorted({shape(found[1]) for s in summaries if (found := parse_reply_summary(s))})


def number_template(model: Model, sender: str | None) -> Template | None:
    """Jo'natuvchining raqam qolipi (o'rganilmagan bo'lsa — None)."""
    data = model.number_templates.get(normalize(sender)) if sender else None
    return Template(**data) if data else None


def learn_model(truths: list[dict], blanks: list[str] | None = None) -> Model:
    """Faqat DEV xatlaridan: boshqarma nomlari, mazmun va jo'natuvchilar (1-sahifa bilan)."""
    by_key: dict[str, list[str]] = {}
    for truth in truths:
        name = expected_boshqarma(truth)
        group = group_of(name)
        key = group if group in ("notariat", "xalqaro") else region_of_boshqarma(name)
        if key:
            by_key.setdefault(key, []).append(name)
    names = {key: most_common(values)[0] for key, values in by_key.items()}
    summaries = [
        (t.get("rekvizit_document") or {}).get("hujjatning_qisqacha_mazmuni") for t in truths
    ]
    sender_texts, sender_names = sender_part(blanks, truths) if blanks else ([], [])
    return Model(
        names,
        most_common(summaries)[0],
        sender_texts,
        sender_names,
        number_part(truths),
        reply_part(truths),
    )


def template_matches(model: Model) -> tuple[int, int]:
    """O'rganilgan viloyat nomlaridan nechtasi shablonga mos (nomlarni ko'rsatmasdan tekshirish)."""
    keys = [k for k in model.names if k in REGION_NAMES]
    same = sum(normalize(model.names[k]) == normalize(template_name(k)) for k in keys)
    return same, len(keys)


def save_model(model: Model, path: Path = MODEL_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(model), ensure_ascii=False, indent=2), encoding="utf-8")


def load_model(path: Path = MODEL_FILE) -> Model:
    """Fayldagi notanish maydonlar e'tiborsiz (kodning boshqa versiyasi saqlagan bo'lsa ham
    ochiladi; yo'q maydonlar — standart qiymat)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Model)}
    return Model(**{key: value for key, value in data.items() if key in known})
