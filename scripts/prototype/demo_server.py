"""B7.3: sahifani soxta ma'lumot bilan ko'rish — real xat ham, real model ham kerak emas.

Vaqtinchalik papkada soxta model (to'qilgan boshqarma nomi) va ikkita to'qilgan xat yasaladi:
- soxta_xat.pdf — testlardagi xat (hamma maydon topiladi);
- soxta_rossiya.pdf — sana yo'q, "№" dan keyin raqam yo'q (go'yo qo'lda yozilgan), hudud modelda
  uchramagan — "tekshirish kerak" holatlarini ko'rsatadi;
- soxta_skaner.pdf — soxta_xat'ning skaneri (matn qatlami yo'q): sana faqat rasmda — sana
  dvigateli (bo'laklar, OCR'lar, ovoz) to'liq ishlaydi.
Tasdiqlangan nomlar ham vaqtinchalik papkaga yoziladi: haqiqiy xotira (outputs/) o'zgarmaydi.
Rahbarga real xatsiz ko'rsatishga qulay.
Server 8001-portda (asosiy 8000 bilan to'qnashmaydi).

Ishga tushirish: poetry run python -m scripts.prototype.demo_server
"""

import tempfile
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

from src.engine.model import Model, save_model
from src.web.api import create_app
from tests.conftest import make_letter_pdf, make_scanned_pdf

PORT = 8001
DEMO_MODEL = Model(
    names={"fargona": "Farg'ona viloyati adliya boshqarmasi (soxta)"},
    summary="Xalqaro huquqiy yordam yuzasidan",
)
RUSSIA = [  # (x, y punktlarda, matn) — hamma ism va raqamlar to'qilgan
    (50, 50, "ГЛАВНОЕ УПРАВЛЕНИЕ"),
    (50, 66, "МИНИСТЕРСТВА ЮСТИЦИИ"),
    (50, 82, "РОССИЙСКОЙ ФЕДЕРАЦИИ"),
    (50, 98, "ПО НИЖЕГОРОДСКОЙ ОБЛАСТИ"),
    (50, 130, "№"),
    (340, 60, "Министерство юстиции"),
    (340, 76, "Республики Узбекистан"),
    (50, 200, "Просим вручить свидетельство о рождении"),
    (50, 216, "гражданину, проживающему: Наманганская область."),
    (50, 700, "Заместитель начальника"),
    (400, 700, "О.Н. Петров"),
]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        letters = folder / "xatlar"
        letters.mkdir()
        save_model(DEMO_MODEL, folder / "model.json")
        make_letter_pdf(letters / "soxta_xat.pdf")
        make_letter_pdf(letters / "soxta_rossiya.pdf", RUSSIA)
        make_scanned_pdf(letters / "soxta_skaner.pdf", letters / "soxta_xat.pdf")

        app = create_app(folder / "model.json", folder / "feedback.jsonl")
        app.mount("/demo", StaticFiles(directory=letters), name="demo")
        print(f"Sahifa: http://127.0.0.1:{PORT}")
        print(f"Soxta xatlar: http://127.0.0.1:{PORT}/demo/soxta_xat.pdf, …/soxta_rossiya.pdf")
        uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
