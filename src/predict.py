"""B4.4: bitta xat uchun AI javobi — hozircha boshqarma va qisqacha mazmun.

"Model" — dev xatlardan o'rganilgan qiymatlar: har hudud (va notariat) uchun boshqarmaning to'liq
nomi va eng ko'p uchraydigan qisqacha mazmun. U outputs/model.json da (gitignore'da) saqlanadi:
nomlarni Claude ko'rmaydi, kod ularni json'lardan o'zi oladi.

Javob shakli — xodim to'ldiradigan json bilan bir xil, ustiga "tekshirish_kerak" ro'yxati.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.baseline import most_common
from src.boshqarma import predict_group
from src.dataset import expected_boshqarma, group_of
from src.evaluate import REKVIZIT_FIELDS, normalize
from src.regions import REGIONS, region_of_boshqarma
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


def learn_model(truths: list[dict]) -> Model:
    """Faqat DEV json'laridan: har kalit uchun eng ko'p uchragan boshqarma nomi va mazmun."""
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
    return Model(names, most_common(summaries)[0])


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
    return {
        "rekvizit_document": rekvizit,
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": [name] if name else []}],
        "tekshirish_kerak": flags,
    }
