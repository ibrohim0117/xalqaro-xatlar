"""B7.2–B7.3: API va sahifa — PDF yuklanadi, AI javobi qaytadi; xodim jo'natuvchini tasdiqlaydi.

GET  /         — sahifa (templates/index.html; CSS va JS — static/, internetdan hech narsa yo'q)
POST /extract  — PDF (+ ixtiyoriy to'g'ri javob json'i — test rejimi) -> AI javobi, vaqt, blank_id,
                 joylar (har maydon qayerdan olingani); ?rasmlar=true — sahifalar rasmi ham
POST /confirm  — {blank_id, nom}: xodim tasdiqlagan jo'natuvchi xotiraga yoziladi

MAXFIYLIK: server faqat 127.0.0.1 da ishlaydi (uvicorn standarti). PDF diskka yozilmaydi —
xotirada qayta ishlanadi. Blank matni faqat RAM'da turadi, brauzerga uning raqami (blank_id)
beriladi; xotira fayliga faqat xodim tasdiqlaganda blank so'zlari yoziladi (raqamlarsiz).

Ishga tushirish: poetry run uvicorn src.web.api:app
"""

import json
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.engine.feedback import FEEDBACK_FILE, confirm_sender
from src.engine.model import MODEL_FILE, Model
from src.engine.pipeline import current_model, process_pdf
from src.evaluation.evaluate import compare
from src.reading.images import page_images

MAX_BLANKS = 1000  # RAM'da turadigan oxirgi blanklar (eskisi o'chadi)
WEB_DIR = Path(__file__).parent  # templates/ va static/ shu yerda


class Confirmation(BaseModel):
    blank_id: str
    nom: str


def read_truth(file: UploadFile) -> dict:
    """Test rejimi: xodim to'ldirgan to'g'ri javob json'i (rekvizit_document, tasks)."""
    try:
        data = json.loads(file.file.read())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"To'g'ri javob json'i o'qilmadi: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("rekvizit_document", {}), dict):
        raise HTTPException(400, "To'g'ri javob json'i kutilgan shaklda emas")
    return data


def create_app(model_file: Path = MODEL_FILE, feedback_file: Path = FEEDBACK_FILE) -> FastAPI:
    app = FastAPI(title="Xalqaro xatlar: rekvizitlar")
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    models: list[Model] = []  # model bir marta yuklanadi; tasdiqdan keyin qayta yuklanadi
    blanks: OrderedDict[str, str] = OrderedDict()

    def model() -> Model:
        if not models:
            try:
                models.append(current_model(model_file, feedback_file))
            except FileNotFoundError as e:
                raise HTTPException(
                    503, "Model yo'q: avval `poetry run python -m scripts.prototype.run_predict`"
                ) from e
        return models[0]

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(WEB_DIR / "templates" / "index.html")

    @app.post("/extract")
    def extract(
        pdf: Annotated[UploadFile, File()],
        truth: Annotated[UploadFile | None, File()] = None,
        rasmlar: bool = False,
    ) -> dict:
        expected = read_truth(truth) if truth is not None else None  # OCR'dan oldin tekshiriladi
        data = pdf.file.read()
        try:
            result = process_pdf(data, model())
        except (pymupdf.FileDataError, ValueError) as e:
            raise HTTPException(400, f"PDF o'qilmadi: {e}") from e
        blank_id = uuid.uuid4().hex
        blanks[blank_id] = result.blank
        if len(blanks) > MAX_BLANKS:
            blanks.popitem(last=False)
        answer = {
            **result.answer,
            "fayl": pdf.filename,
            "vaqt": {
                "jami": round(result.seconds, 2),
                "ocr": round(result.ocr.seconds, 2),
                "ocr_soni": result.ocr.calls,
                "sahifalar": result.pages,
            },
            "blank_id": blank_id,
            "joylar": result.boxes,
        }
        if rasmlar:  # sahifa uchun: PDF ustida ramkalar chiziladi
            answer["rasmlar"] = page_images(data, result.pages)
        if expected is not None:
            answer["solishtirish"] = compare(result.answer, expected)
        return answer

    @app.post("/confirm")
    def confirm(body: Confirmation) -> dict:
        blank = blanks.get(body.blank_id)
        if blank is None:
            raise HTTPException(
                404, "Blank topilmadi: server qayta yoqilgan bo'lsa, xatni qayta yuklang"
            )
        name = body.nom.strip()
        if not name:
            raise HTTPException(400, "Nom bo'sh")
        confirm_sender(blank, name, feedback_file)
        models.clear()  # keyingi xatda yangi tasdiq bilan qayta yuklanadi
        return {"saqlandi": True}

    return app


app = create_app()
