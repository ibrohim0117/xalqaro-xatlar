"""src/reading/cv_safe.py — OpenCV resize qulashiga chora (to'qilgan rasmlar bilan)."""

import subprocess
import sys

import cv2
import numpy as np

import src.reading  # noqa: F401 — chorani o'rnatadi
from src.reading.cv_safe import _original_resize, safe_resize

CRASH = """
import numpy as np
{setup}
import cv2
src = np.empty((1088, 768, 3), np.uint8)
src[:] = 7
cv2.resize(src, (566, 1087))
"""


def run(setup: str) -> int:
    code = CRASH.format(setup=setup)
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode


def test_resize_crash_is_avoided():
    # chorasiz bu o'lcham OpenCV 5.0 (arm64) da qulatadi; boshqa platformada qulamasligi mumkin
    assert run("import src.reading") == 0


def test_cv2_resize_is_replaced():
    assert cv2.resize is safe_resize


def test_safe_resize_gives_the_same_result():
    rng = np.random.default_rng(1)
    for h, w, size in [(37, 101, (60, 20)), (480, 640, (320, 240)), (5, 5, (50, 50))]:
        image = rng.integers(0, 255, (h, w, 3), np.uint8)
        assert np.array_equal(safe_resize(image, size), _original_resize(image, size))
    gray = rng.integers(0, 255, (100, 80), np.uint8)
    scaled = safe_resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    expected = _original_resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    assert np.array_equal(scaled, expected)
