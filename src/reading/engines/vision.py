"""B5.14: Apple Vision — macOS'ning o'z OCR'i (iPhone "Live Text" bilan bir xil texnologiya).

To'liq oflayn: rasm kompyuterdan chiqmaydi. Faqat macOS'da (pyobjc-framework-Vision). Tillar:
rus, ukrain, ingliz (macOS 26 da o'zbek yo'q). "№" ni ko'pincha "Nº" deb o'qiydi — date_vote va
number_vote buni taniydi. Qo'lyozma raqamlarni VLM'dan yaxshiroq o'qiydimi — o'lchanadi
(compare_ocr, number_failures).
"""

import re

from src.reading.pdf_text import Word

LANGUAGES = ("ru-RU", "uk-UA", "en-US")
# Vision bo'lagi (0..1): yuqoridan, chapdan, balandlik, kenglik, matn
Observation = tuple[float, float, float, float, str]


def group_lines(boxes: list[tuple[float, float, float, str]]) -> list[str]:
    """Bo'laklar (yuqoridan masofa, chapdan masofa, balandlik, matn) -> qatorlar: markazlari
    yarim balandlikdan yaqin bo'laklar bitta qator, qator ichida chapdan o'ngga."""
    lines: list[list[tuple[float, float, float, str]]] = []
    for box in sorted(boxes):
        top, _, height, _ = box
        last = lines[-1] if lines else None
        if last and abs((top + height / 2) - (last[0][0] + last[0][2] / 2)) < height / 2:
            last.append(box)
        else:
            lines.append([box])
    return [" ".join(text for _, _, _, text in sorted(line, key=lambda b: b[1])) for line in lines]


def to_words(
    found: list[Observation], region: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
) -> list[Word]:
    """Vision bo'laklari -> sahifa koordinatalaridagi so'zlar (imzo qoidasi shular bilan ishlaydi).
    region — rasm sahifaning qaysi qismi (x0, y0, x1, y1; 0..1). Har bo'lak — bitta qator; so'z
    o'rni bo'lak ichidagi harflar ulushi bo'yicha (taxminiy)."""
    rx0, ry0, rx1, ry1 = region
    sx, sy = rx1 - rx0, ry1 - ry0
    words = []
    for line, (top, left, height, width, text) in enumerate(sorted(found)):
        total = max(len(text), 1)
        for m in re.finditer(r"\S+", text):
            x0, x1 = left + width * m.start() / total, left + width * m.end() / total
            box = (rx0 + x0 * sx, ry0 + top * sy, rx0 + x1 * sx, ry0 + (top + height) * sy)
            words.append(Word(m[0], *box, line))
    return words


class VisionReader:
    name = "apple-vision"

    def __init__(self, languages: tuple[str, ...] = LANGUAGES, correction: bool = False):
        """correction — til lug'ati bilan tuzatish; raqam va qisqartmalar buzilmasin — o'chiq."""
        import objc  # faqat macOS: boshqa tizimda bu yerda ImportError
        import Vision
        from Foundation import NSData

        self._objc, self._vision, self._nsdata = objc, Vision, NSData
        self.languages, self.correction = list(languages), correction

    def read(self, png: bytes) -> str:
        found = self.observations(png)
        return "\n".join(group_lines([(t, x, h, text) for t, x, h, _, text in found]))

    def observations(self, png: bytes) -> list[Observation]:
        """Rasmdagi matn bo'laklari joylashuvi bilan (0..1, boshi — yuqori chap burchak)."""
        vision = self._vision
        with self._objc.autorelease_pool():  # har chaqiruvdan keyin macOS obyektlari bo'shatiladi
            data = self._nsdata.dataWithBytes_length_(png, len(png))
            handler = vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
            request = vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(vision.VNRequestTextRecognitionLevelAccurate)
            request.setRecognitionLanguages_(self.languages)
            request.setUsesLanguageCorrection_(self.correction)
            ok, error = handler.performRequests_error_([request], None)
            if not ok:
                raise RuntimeError(f"Vision o'qimadi: {error}")
            boxes = []
            for observation in request.results() or []:
                candidates = observation.topCandidates_(1)
                if candidates:
                    box = observation.boundingBox()  # 0..1, boshi — pastki chap burchak
                    top = 1 - box.origin.y - box.size.height
                    text = str(candidates[0].string())
                    boxes.append((top, box.origin.x, box.size.height, box.size.width, text))
        return boxes
