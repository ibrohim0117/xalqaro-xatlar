"""OpenCV 5.0 (arm64, KleidiCV) cv2.resize xatosiga chora.

Xato: manba rasm buferi xotira sahifasi chegarasida tugasa, resize buferdan tashqarini o'qiydi va
jarayon qulaydi (SIGSEGV). 25.10 papka rejimida API serverini shu qulatgan (macOS hisoboti:
kleidicv_resize_generic_stripe_u8, RapidOCR ichidan). To'qilgan rasmda takrorlanadi:
1088x768x3 -> 566x1087 har safar qulaydi; cv2.setNumThreads(1) va setUseOptimized(False) yordam
bermaydi.
Chora: manba bir qator zaxirasi bor buferga ko'chiriladi va resize uning ko'rinishiga beriladi —
ortiqcha o'qish zaxiraga tushadi, natija o'zgarmaydi (sinov: 60 000 xavfli o'lchamda qulash 0).
RapidOCR cv2.resize'ni modul orqali chaqiradi, shuning uchun cv2.resize almashtiriladi (install).
"""

import cv2
import numpy as np

_original_resize = cv2.resize


def safe_resize(src, *args, **kwargs):
    """cv2.resize bilan bir xil, lekin manba oxirida bir qator zaxira bor."""
    src = np.asarray(src)
    if src.ndim < 2 or src.size == 0:
        return _original_resize(src, *args, **kwargs)
    padded = np.empty((src.shape[0] + 1, *src.shape[1:]), src.dtype)
    padded[: src.shape[0]] = src
    return _original_resize(padded[: src.shape[0]], *args, **kwargs)


def install() -> None:
    """cv2.resize ni safe_resize bilan almashtiradi (qayta chaqirilsa — o'zgarmaydi)."""
    cv2.resize = safe_resize
