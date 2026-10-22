"""Real xatlar to'plami bilan ishlash: ro'yxat, to'g'ri javoblar (json) va dev/test bo'linishi.

MAXFIYLIK: bu modul real fayllarni faqat o'qiydi va hech narsani ekranga chiqarmaydi.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

REAL_DIR = Path("data/real")
SPLIT_FILE = REAL_DIR / "split.json"  # data/real ichida — gitga kirmaydi


@dataclass(frozen=True)
class Letter:
    doc_id: str  # papka nomi, masalan "DOC_3142589"
    pdf: Path
    truth: Path  # to'g'ri javoblar (json)


def list_letters(root: Path = REAL_DIR) -> list[Letter]:
    """PDF va json'i bor barcha xatlar, papka nomi bo'yicha tartiblangan."""
    letters = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        pdf = next(folder.glob("*.pdf"), None)
        truth = next(folder.glob("*.json"), None)
        if pdf and truth:
            letters.append(Letter(folder.name, pdf, truth))
    return letters


def load_truth(letter: Letter) -> dict:
    return json.loads(letter.truth.read_text(encoding="utf-8"))


def expected_boshqarma(truth: dict) -> str | None:
    """Kutilgan boshqarma: `asosiy_ijrochilar_boshqarmalari` to'la bo'lsa o'sha,
    bo'sh bo'lsa `asosiy_ijrochilar` (u yerda viloyat adliya boshqarmasi turadi).

    Bu qoida 100 ta json tahlilidan chiqdi; rahbardan tasdiq kutilmoqda.
    """
    task = (truth.get("tasks") or [{}])[0]
    names = task.get("asosiy_ijrochilar_boshqarmalari") or task.get("asosiy_ijrochilar") or []
    return names[0] if names else None


def group_of(boshqarma: str | None) -> str:
    """Boshqarmaning guruhi: bo'linish va hisobotda ishlatiladi."""
    low = (boshqarma or "").lower()
    if "xalqaro" in low:
        return "xalqaro"
    if "notariat" in low:
        return "notariat"
    if "adliya" in low:
        return "viloyat"
    return "noma'lum"


def make_split(letters: list[Letter], test_share: float = 0.3, seed: int = 42) -> dict:
    """Har bir guruhdan o'z ulushiga qarab test'ga ajratadi (stratifikatsiya)."""
    by_group: dict[str, list[str]] = {}
    for letter in letters:
        group = group_of(expected_boshqarma(load_truth(letter)))
        by_group.setdefault(group, []).append(letter.doc_id)

    rng = random.Random(seed)
    split = {"seed": seed, "test_share": test_share, "dev": [], "test": []}
    for group in sorted(by_group):
        ids = sorted(by_group[group])
        rng.shuffle(ids)
        n_test = round(len(ids) * test_share)
        split["test"] += sorted(ids[:n_test])
        split["dev"] += sorted(ids[n_test:])
    return split


def load_split() -> dict:
    return json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
