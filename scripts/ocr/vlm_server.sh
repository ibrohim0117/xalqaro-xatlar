#!/bin/sh
# B5.3b: VLM serveri (standart Qwen3.5-2B, mlx-vlm) — alohida .venv-vlm muhitida, FAQAT shu kompyuterda.
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
# Boshqa model (masalan 4B sinovi, ~3 GB):
#   .venv-vlm/bin/hf download mlx-community/Qwen3.5-4B-4bit --local-dir models/vlm/Qwen3.5-4B-4bit
#   VLM_MODEL=models/vlm/Qwen3.5-4B-4bit VLM_ARGS="--vision-cache-size 1 --prefill-step-size 512" \
#     sh scripts/ocr/vlm_server.sh
# VLM_ARGS — qo'shimcha sozlamalar. Xotirani tejash (8 GB Mac; 4B birinchi urinishda Mac'ni qulatgan):
# --vision-cache-size 1 (standart 20 ta rasm tahlili xotirada turadi — bizda har bo'lak yangi rasm,
# keshdan foyda yo'q), --prefill-step-size 512 (rasm modelga 2048 emas, 512 tokendan beriladi —
# xotira cho'qqisi pasayadi). Natijaga ta'sir qilmaydi.

cd "$(dirname "$0")/../.." || exit 1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
# --log-level WARNING: har 10 tokendagi INFO yozuvlari chiqmasin
# shellcheck disable=SC2086  # VLM_ARGS ataylab so'zlarga bo'linadi
exec .venv-vlm/bin/python -m mlx_vlm.server \
    --model "${VLM_MODEL:-models/vlm/Qwen3.5-2B-4bit}" \
    --host 127.0.0.1 \
    --port "${VLM_PORT:-8090}" \
    --log-level WARNING \
    ${VLM_ARGS:-}
