"""B7.2: ishlab turgan API'ni real dev xatlarda tekshirish (HTTP orqali, brauzer o'rniga).

Har xat PDF'i to'g'ri javob json'i bilan birga POST /extract ga yuboriladi (test rejimi).
Ekranga FAQAT vaqt va har maydon belgisi chiqadi: ✓ to'g'ri, ✗ xato, – AI yozmagan
(qavsda t✓ — taklif to'g'ri). Qiymatlar chiqmaydi. /confirm chaqirilmaydi (xotira o'zgarmaydi).

Avval server: poetry run uvicorn src.web.api:app
Keyin:        poetry run python -m scripts.prototype.check_api --limit 3
"""

import argparse

import httpx

from src.common.schema import ALL_FIELDS
from src.evaluation.dataset import list_letters, load_split

SHORT = {  # ustun nomlari qisqa bo'lsin
    "hujjat_junatuvchi_tashkilot": "jo'natuvchi",
    "hujjat_sana": "sana",
    "hujjat_raqami": "raqam",
    "imzolagan_shaxs": "imzo",
    "hujjatning_qisqacha_mazmuni": "mazmun",
    "boshqarma": "boshqarma",
}


def mark(row: dict) -> str:
    sign = {True: "✓", False: "✗", None: "–"}[row["mos"]]
    if "taklif_mos" in row:
        sign += " (t✓)" if row["taklif_mos"] else " (t✗)"
    return sign


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3, help="nechta dev xat")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])[: args.limit]
    for i, doc_id in enumerate(dev, 1):
        letter = letters[doc_id]
        files = {
            "pdf": ("xat.pdf", letter.pdf.read_bytes(), "application/pdf"),
            "truth": ("xat.json", letter.truth.read_bytes(), "application/json"),
        }
        response = httpx.post(f"{args.url}/extract", files=files, timeout=120)
        response.raise_for_status()
        body = response.json()
        t = body["vaqt"]
        print(
            f"{i:>2}. {t['jami']:5.1f} s (OCR {t['ocr']:5.1f} s, {t['ocr_soni']} marta, "
            f"{t['sahifalar']} sahifa)\n    "
            + " | ".join(f"{SHORT[f]} {mark(body['solishtirish'][f])}" for f in ALL_FIELDS)
        )


if __name__ == "__main__":
    main()
