"""Model — dev xatlardan o'rganilgan qiymatlar: har hudud (va notariat) uchun boshqarmaning to'liq
nomi, eng ko'p uchraydigan qisqacha mazmun va jo'natuvchini topish uchun dev xatlari blankining
so'zlari (blankda fuqaro ismi yo'q; telefon va raqamlar saqlanmaydi) hamda jo'natuvchi nomlari.
U outputs/model.json da (gitignore'da) saqlanadi: nomlarni Claude ko'rmaydi.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.common.text import most_common, normalize
from src.fields.regions import REGIONS, region_of_boshqarma
from src.fields.sender import blank_words

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
