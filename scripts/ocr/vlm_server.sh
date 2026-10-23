#!/bin/sh
# B5.3b: VLM serveri (Qwen3.5-2B, mlx-vlm) — alohida .venv-vlm muhitida, FAQAT shu kompyuterda.
#
# MAXFIYLIK: mlx-vlm standart holatda 0.0.0.0 da ochiladi (tarmoqdagi hamma ulanadi) — shuning uchun
# --host 127.0.0.1. HF_HUB_OFFLINE va TRANSFORMERS_OFFLINE: model faqat models/vlm dan, internetga chiqmaydi.
# Nega alohida muhit: mlx-vlm opencv-python, rapidocr esa opencv-python-headless talab qiladi — bitta
# muhitda bir-birini buzadi. Bizning kod serverga src/reading/engines/vlm.py orqali murojaat qiladi.
#
# O'rnatish (bir marta):
#   python3.13 -m venv .venv-vlm && .venv-vlm/bin/pip install mlx-vlm==0.7.10
#   .venv-vlm/bin/hf download mlx-community/Qwen3.5-2B-4bit --local-dir models/vlm/Qwen3.5-2B-4bit
# Ishga tushirish: sh scripts/ocr/vlm_server.sh   (to'xtatish — Ctrl+C)

cd "$(dirname "$0")/../.." || exit 1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec .venv-vlm/bin/python -m mlx_vlm.server \
    --model models/vlm/Qwen3.5-2B-4bit \
    --host 127.0.0.1 \
    --port "${VLM_PORT:-8090}" \
    --log-level warning  # har 10 tokendagi INFO yozuvlari chiqmasin
