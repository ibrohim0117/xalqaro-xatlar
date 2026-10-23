"""RapidOCR (PP-OCR, ONNX) — avval matn qatorlarini topadi (detection), keyin har birini o'qiydi.

Shuning uchun ko'p qatorli bo'lakni ham o'qiydi (Tesseract --psm 7 dan farqli).
Modellar (internetga chiqmaydi — yo'llar aniq beriladi, yo'nalish modeli o'chirilgan):
- qatorlarni topish: paket ichidagi PP-OCRv6_det_small (ko'p tilli);
- o'qish "v6": paket ichidagi PP-OCRv6_rec_small — lotin tillari va raqamlar (kirill yo'q);
- o'qish "eslav": models/rapidocr/eslav_PP-OCRv5_rec_mobile.onnx — rus/ukrain/belarus (RapidAI
  rasmiy manbasi, v3.10.0, SHA256 08705d67…89aab).
"""

from pathlib import Path

import cv2
import numpy as np
from rapidocr import RapidOCR

MODELS_DIR = Path(__file__).resolve().parents[3] / "models" / "rapidocr"
ESLAV = MODELS_DIR / "eslav_PP-OCRv5_rec_mobile.onnx"
THREADS = -1  # barcha yadrolar — eng tez; kuller ishlashi mumkin (Ibrohim: aniqlik muhimroq)
ESLAV_URL = (  # rasmiy manba; yuklab olingach SHA256 tekshiriladi (yuqorida)
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/"
    "eslav_PP-OCRv5_rec_mobile.onnx"
)


class RapidReader:
    name = "rapidocr"

    def __init__(self, rec: str = "v6", threads: int = THREADS):
        params = {
            "Global.use_cls": False,
            "Global.log_level": "warning",
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
        }
        if rec == "eslav":
            if not ESLAV.exists():
                raise FileNotFoundError(f"{ESLAV} yo'q. Yuklab olish: {ESLAV_URL}")
            params["Rec.model_path"] = str(ESLAV)
        self.engine = RapidOCR(params=params)

    def read(self, png: bytes) -> str:
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        result = self.engine(image)
        return "\n".join(result.txts or ())  # qatorlar yuqoridan pastga (RapidOCR tartiblaydi)
