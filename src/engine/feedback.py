"""B5.1c: qayta aloqa — xodim tasdiqlagan jo'natuvchi nomlari xotirasi.

Xodim AI javobini tasdiqlasa yoki tuzatsa, xat blankining so'zlari va to'g'ri nom shu faylga
yoziladi. Keyingi xatda jo'natuvchi dev namunalari bilan birga shu yozuvlar orasidan ham qidiriladi:
tashkilot bir marta tasdiqlangach, uning keyingi xatlari avtomatik taniladi.

MAXFIYLIK: faqat blank so'zlari (tashkilot matni) saqlanadi — fuqaro ismi, telefon, raqam yo'q.
Fayl outputs/ da (gitignore'da).
"""

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from src.engine.model import Model
from src.fields.sender import blank_words

FEEDBACK_FILE = Path("outputs/feedback.jsonl")


def confirm_sender(blank: str, name: str, path: Path = FEEDBACK_FILE) -> None:
    """Xodim tasdiqlagan nomni xotiraga qo'shadi (har yozuv — fayldagi bitta qator)."""
    record = {
        "blank": blank_words(blank),
        "nom": name,
        "vaqt": datetime.now().isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_confirmed(path: Path = FEEDBACK_FILE) -> tuple[list[str], list[str]]:
    """(blank so'zlari, nomlar) — tasdiqlangan hamma yozuvlar."""
    if not path.exists():
        return [], []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [r["blank"] for r in records], [r["nom"] for r in records]


def with_confirmed(model: Model, blanks: list[str], names: list[str]) -> Model:
    """Model + tasdiqlangan namunalar (model o'zgarmaydi — yangi nusxa qaytadi)."""
    return replace(
        model,
        sender_texts=model.sender_texts + blanks,
        sender_names=model.sender_names + names,
    )
