"""B5.5: raqam — bir necha OCR o'qigan matndan (sana ovozi kabi: fields/date_vote).

Har OCR o'z bo'laklaridan (number, line, header, page) raqam nomzodlarini beradi:
  - VLM aniq savol bilan JSON qaytaradi — raqam uning "raqam" maydonidan;
  - ko'p qatorli matnda (header, page) — faqat "№" (No/N) bor qatordan; "На № … от …" qatori emas
    (u bizning oldingi xatimizning raqami);
  - bitta qatorli bo'lakda (number, line) — butun matndan.
Solishtirish bo'shliqsiz, kichik harf bilan (number_template.key) — evaluate.compare kabi.

Qoida (number_reading; dev 70, B5.5, qolip — tashkilotning boshqa xatlaridan): hamma raqamlar
tashkilot qolipiga moslanadi; VLM aniq savol header'dan topgan raqam boshqa OCR yoki matn qatlami
tasdiqlasa — "tekshiring" belgisi bilan yoziladi (12 tadan 11 to'g'ri). Eski VLM (ko'chirish)
tasdig'i HISOB EMAS: bir model xatosini takrorlaydi (u yolg'iz tasdiqlagan 5 tadan 5 tasi xato
edi). Takliflar — top-3.
"""

import json
import re
from collections import Counter

from src.fields.date_number import parse_number
from src.fields.date_vote import ANCHOR_TOKEN
from src.fields.number_template import Template, fit_all, key

JSON = re.compile(r"\{.*\}", re.DOTALL)
GLUE = re.compile(r"\s*([/\-])\s*")  # "54/07 - 16606" -> "54/07-16606"
REPLY = re.compile(r"(?:^|\s)(?:на|ha)\s*(?:№|n[oо°º]?\b)", re.IGNORECASE)  # "На № … от …"
MULTI_LINE = ("header", "page")  # ko'p qatorli bo'laklar
FINDER = "vlm-extract"  # raqamni topuvchi: VLM aniq savol, header bo'lagi
SAME_MODEL = {"vlm"}  # topuvchi bilan bir model (ko'chirish) — uning tasdig'i hisob emas


def vlm_answer(text: str) -> dict | None:
    """VLM aniq savol javobi (JSON); oddiy matn bo'lsa — None."""
    found = JSON.search(text)
    if not found:
        return None
    try:
        answer = json.loads(found[0])
    except json.JSONDecodeError:
        return None
    return answer if isinstance(answer, dict) else None


def anchor_number(text: str) -> str | None:
    """Ko'p qatorli matnda "№" (No/N) bor qatordagi raqam ("На №" qatori emas)."""
    for line in text.splitlines():
        if ANCHOR_TOKEN.search(line) and not REPLY.search(line) and (number := parse_number(line)):
            return number
    return None


def read_number(crop: str, text: str) -> str | None:
    """Bitta bo'lak matnidan raqam."""
    if (answer := vlm_answer(text)) is not None:
        value = answer.get("raqam")
        return parse_number(GLUE.sub(r"\1", str(value))) if value else None
    return anchor_number(text) if crop in MULTI_LINE else parse_number(text)


def engine_numbers(texts: dict[str, str]) -> dict[str, str | None]:
    """Bitta OCR'ning bo'laklaridan raqam nomzodlari (date bo'lagi — "№" dan chapi, raqam yo'q)."""
    return {crop: read_number(crop, text) for crop, text in texts.items() if crop != "date"}


def confirmed_number(
    found: list[dict[str, str | None]], first_keys: tuple[str, ...] = ("header",)
) -> str | None:
    """1-OCR raqami (first_keys bo'laklaridan) — boshqa OCR'lardan biri ham uni ko'rgan bo'lsa."""
    first = next((found[0][k] for k in first_keys if found[0].get(k)), None)
    if not first:
        return None
    seen = any(key(first) in {key(v) for v in f.values() if v} for f in found[1:])
    return first if seen else None


def ranked_numbers(found: list[dict[str, str | None]], k: int = 3) -> list[str]:
    """Takliflar: ko'proq OCR ko'rgan raqam oldinda (har OCR — bitta ovoz), ko'pi bilan k ta."""
    counts, shown = Counter(), {}
    for f in found:
        numbers = {key(v): v for v in f.values() if v and key(v)}
        counts.update(numbers.keys())
        for number_key, value in numbers.items():
            shown.setdefault(number_key, value)
    return [shown[number_key] for number_key, _ in counts.most_common(k)]


def number_reading(
    readers: list[str],
    found: list[dict[str, str | None]],
    text: dict[str, str | None],
    template: Template | None,
) -> tuple[str | None, list[str]]:
    """(tekshiring belgisi bilan yoziladigan raqam, takliflar). readers — ishlagan OCR'lar nomi,
    found — ularning raqamlari (engine_numbers), text — matn qatlami va sahifa OCR'idagi raqam."""
    found = [fit_all(f, template) for f in found]
    text = fit_all(text, template)
    voters = [f for name, f in zip(readers, found, strict=True) if name not in SAME_MODEL]
    prefill = confirmed_number([*voters, text]) if readers[:1] == [FINDER] else None
    return prefill, ranked_numbers([*found, text])
