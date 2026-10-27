"""Vaqt: bitta xatga ketgan vaqt qayerga sarflanadi — bosqichlar va OCR'lar bo'yicha (faqat sonlar).

Prototip zanjiri (pipeline.process_pdf) aynan o'zi ishlaydi; har OCR o'lchagich bilan o'raladi va
har o'qish qaysi bo'lak (header, page, line, date, number) uchun ekani belgilanadi — natija
o'zgarmaydi. Ekranga faqat soniyalar va sonlar chiqadi.

Javoblar outputs/vaqt/<nom>/<DOC>.json ga yoziladi (gitignore'da). Tezlashtirishdan keyin --compare
bilan solishtiriladi: "sifatga ta'sir qilmadi" = har xatning javobi AYNAN bir xil. Ekranga faqat
DOC raqami va farq qilgan maydon NOMI chiqadi. Avval kodni o'zgartirmasdan ikki marta ishga
tushirib (oldin, oldin2) solishtirish kerak: zanjirning o'zi har safar bir xil javob beradimi.
DIQQAT (vaqt uchun): kichik to'plamni ketma-ket qayta o'lchaganda ikkinchisi ancha tez chiqishi
mumkin (soxta 4 xat: median 29.9 -> 18.6 s; sababi aniqlanmagan — VLM keshi yoki xotira qizishi).
Real 10 xatda bunday farq bo'lmadi (27.10: VLM header 11.1 va 10.9 s). Vaqtlarni bir xil sharoitda
va kamida 10 xatda solishtiring (javoblarga ta'sir qilmaydi — faqat soniyalarga).

DIQQAT (javoblar uchun): sana takliflarida ovozi teng sanalar tartibi har ishga tushirishda
boshqacha bo'lishi mumkin (date_vote.ranked: set tartibi Python hash'iga bog'liq) — o'zgarishsiz
kod ham boshqa taklif berishi mumkin. Aniq solishtirish uchun ikkala o'lchov ham PYTHONHASHSEED=0
bilan; --sequential — OCR'lar eskicha bitta navbatda (parallel yo'laklarsiz).

Ishga tushirish (VLM yoqilgan bo'lsin — make vlm; sahifa serveri shart emas):
    poetry run python -m scripts.prototype.measure_time outputs/papkalar/real2_25 --name oldin
    poetry run python -m scripts.prototype.measure_time --compare oldin oldin2
    PYTHONHASHSEED=0 poetry run python -m scripts.prototype.measure_time <papka> --name eski0 \
        --sequential
"""

import argparse
import json
import statistics
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from time import perf_counter

from src.common.schema import REKVIZIT_FIELDS
from src.engine import date_ocr
from src.engine.date_ocr import DateOcr, build_date_ocr
from src.engine.pipeline import current_model, process_pdf
from src.evaluation.dataset import list_letters, load_truth
from src.fields.date_vote import to_day

OUT_DIR = Path("outputs/vaqt")
SIGNER = "imzo"  # Apple Vision imzo zaxirasi (signer_ocr) — bo'lak emas, alohida o'qish
CUT = "kesish"  # log'da OCR o'rnida: bo'lakni sahifadan kesish vaqti


class Crop(bytes):
    """PNG bo'lagi va uning nomi — o'lchagich qaysi bo'lak o'qilganini bilsin."""

    name = "?"


@contextmanager
def tagged_crops(log: dict[tuple[str, str], float] | None = None) -> Iterator[None]:
    """date_ocr kesgan bo'laklarga nom qo'yadi (ocr_regions kaliti) va kesish vaqtini log'ga
    yozadi; chiqishda asli tiklanadi."""
    regions, crop_png = date_ocr.ocr_regions, date_ocr.crop_png
    names: dict[int, str] = {}

    def named_regions(first):
        found = regions(first)
        names.clear()
        names.update({id(box): name for name, box in found.items()})
        return found

    def named_crop(page, box, **kwargs):
        start = perf_counter()
        png = Crop(crop_png(page, box, **kwargs))
        png.name = names.get(id(box), "?")
        if log is not None:
            log[CUT, png.name] += perf_counter() - start
        return png

    date_ocr.ocr_regions, date_ocr.crop_png = named_regions, named_crop
    try:
        yield
    finally:
        date_ocr.ocr_regions, date_ocr.crop_png = regions, crop_png


class Timed:
    """OCR o'ramasi: har o'qish vaqti (OCR, bo'lak) bo'yicha yig'iladi; javob o'zgarmaydi."""

    def __init__(self, reader, log: dict[tuple[str, str], float]):
        self.reader, self.name, self.log = reader, reader.name, log

    def _timed(self, crop: str, call, png: bytes):
        start = perf_counter()
        try:
            return call(png)
        finally:
            self.log[self.name, crop] += perf_counter() - start

    def read(self, png: bytes) -> str:
        return self._timed(getattr(png, "name", "?"), self.reader.read, png)

    def observations(self, png: bytes):  # faqat Apple Vision'da bor (imzo zaxirasi)
        return self._timed(SIGNER, self.reader.observations, png)


@dataclass
class Row:
    """Bitta xat: soniyalar."""

    total: float
    page_ocr: float  # Tesseract: 1-sahifa va matn qatlami yo'q / sifatsiz sahifalar
    crops: float  # sana dvigateli: bo'laklarni kesish + hamma OCR'lar (imzo zaxirasisiz)
    reads: dict[tuple[str, str], float] = field(default_factory=dict)  # (OCR, bo'lak) -> soniya
    pages: int = 0
    auto_date: bool = False  # sana matn qatlamidan: bo'lak OCR'lari faqat raqam uchun ishlaydi

    @property
    def signer(self) -> float:
        return sum(s for (_, crop), s in self.reads.items() if crop == SIGNER)

    @property
    def cutting(self) -> float:
        return sum(s for (reader, _), s in self.reads.items() if reader == CUT)

    @property
    def reading(self) -> float:
        """Bo'lak OCR'lari soat bo'yicha: OCR'lar parallel ishlasa, ularning yig'indisidan kam."""
        return self.crops - self.cutting

    @property
    def rest(self) -> float:
        return self.total - self.page_ocr - self.crops - self.signer


def received_of(truth: dict) -> Date:
    """Xat kelgan sana — sahifa (api.received_date) kabi: json'dagi kirish_sana, bo'lmasa bugun."""
    return to_day((truth.get("rekvizit_document") or {}).get("kirish_sana")) or Date.today()


@contextmanager
def one_lane(enabled: bool) -> Iterator[None]:
    """enabled bo'lsa — hamma OCR bitta navbatda (parallel yo'laklardan oldingi tartib)."""
    lane_of = date_ocr.lane_of
    if enabled:
        date_ocr.lane_of = lambda name: "bitta"
    try:
        yield
    finally:
        date_ocr.lane_of = lane_of


def measure(folder: Path, name: str, limit: int | None, sequential: bool = False) -> list[Row]:
    letters = list_letters(folder)[:limit]
    out = OUT_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    log: dict[tuple[str, str], float] = defaultdict(float)
    model = current_model()
    rows = []
    with tagged_crops(log), one_lane(sequential):
        engine = build_date_ocr()
        timed = DateOcr([Timed(r, log) for r in engine.readers]) if engine else None
        for i, letter in enumerate(letters, 1):
            print(f"\r  {i}/{len(letters)} xat…", end="", flush=True)
            log.clear()
            received = received_of(load_truth(letter))
            result = process_pdf(letter.pdf.read_bytes(), model, timed, received)
            text = json.dumps(result.answer, ensure_ascii=False, sort_keys=True, indent=1)
            (out / f"{letter.doc_id}.json").write_text(text, encoding="utf-8")
            reading = result.date
            rows.append(
                Row(
                    total=result.seconds,
                    page_ocr=result.ocr.seconds,
                    crops=reading.seconds if reading else 0.0,
                    reads=dict(log),
                    pages=result.pages,
                    auto_date=bool(reading and reading.auto),
                )
            )
    print("\r" + " " * 30 + "\r", end="")
    return rows


def stats(values: list[float]) -> str:
    """median | o'rtacha | jami (soniya)."""
    if not values:
        return f"{'—':>8}{'—':>10}{'—':>9}"
    return f"{statistics.median(values):8.1f}{statistics.mean(values):10.1f}{sum(values):9.0f}"


def report(rows: list[Row], folder: Path, name: str) -> None:
    n = len(rows)
    if not n:
        print(f"{folder}: PDF va json'i bor xat topilmadi")
        return
    total = sum(r.total for r in rows) or 1.0
    readers = list(dict.fromkeys(reader for r in rows for reader, _ in r.reads if reader != CUT))
    print(f"Vaqt: {n} xat ({folder}), javoblar: {OUT_DIR / name}/")
    print(f"  sanasi bosma (bo'lak OCR faqat raqam uchun): {sum(r.auto_date for r in rows)} xat")
    print(f"  o'qilgan sahifalar: median {statistics.median(r.pages for r in rows):.0f}\n")
    print(f"  {'bosqich, soniya':<34}{'median':>8}{'o`rtacha':>10}{'jami':>9}{'ulushi':>9}")

    def line(label: str, values: list[float]) -> None:
        print(f"  {label:<34}{stats(values)}{sum(values) / total:9.0%}")

    line("hammasi", [r.total for r in rows])
    line("sahifa OCR (Tesseract)", [r.page_ocr for r in rows])
    line("bo'laklarni kesish", [r.cutting for r in rows])
    line("bo'lak OCR'lari (soat bo'yicha)", [r.reading for r in rows])
    for reader in readers:  # har OCR o'zi: parallel ishlasa, yig'indisi yuqoridagidan ko'p
        per_letter = [
            sum(s for (o, c), s in r.reads.items() if o == reader and c != SIGNER) for r in rows
        ]
        if any(per_letter):
            line(f"  {reader}", per_letter)
    line("imzo (Apple Vision zaxirasi)", [r.signer for r in rows])
    line("qolgani (matn qatlami, qoidalar)", [r.rest for r in rows])

    print("\n  Bo'lak bo'yicha (median soniya, faqat o'qilgan xatlarda; qavsda — nechta xat):")
    for reader in readers:
        crops = list(dict.fromkeys(c for r in rows for o, c in r.reads if o == reader))
        cells = []
        for crop in crops:
            values = [r.reads[reader, crop] for r in rows if (reader, crop) in r.reads]
            cells.append(f"{crop} {statistics.median(values):.1f} ({len(values)})")
        print(f"    {reader:<18}" + " | ".join(cells))


def tips_difference(a, b) -> str:
    """Takliflar farqi turi, qiymatlarsiz: bir xil takliflar boshqa tartibda yoki tarkib boshqa."""
    left = [str(v) for v in (a if isinstance(a, list) else [a] if a else [])]
    right = [str(v) for v in (b if isinstance(b, list) else [b] if b else [])]
    if sorted(left) == sorted(right):
        return "faqat tartib"
    common = len(set(left) & set(right))
    return f"tarkib: umumiy {common}, {len(left)} va {len(right)} ta"


def changed_fields(a: dict, b: dict) -> list[str]:
    """Ikki javob qaysi maydonlarda farq qiladi — faqat NOMLARI (qiymatlar chiqmaydi)."""
    changed = []
    doc_a, doc_b = a.get("rekvizit_document") or {}, b.get("rekvizit_document") or {}
    changed += [f for f in REKVIZIT_FIELDS if doc_a.get(f) != doc_b.get(f)]
    if a.get("tasks") != b.get("tasks"):
        changed.append("boshqarma")
    if a.get("tekshirish_kerak") != b.get("tekshirish_kerak"):
        changed.append("tekshirish_kerak")
    tips_a, tips_b = a.get("takliflar") or {}, b.get("takliflar") or {}
    changed += [
        f"takliflar.{k} ({tips_difference(tips_a.get(k), tips_b.get(k))})"
        for k in sorted(set(tips_a) | set(tips_b))
        if tips_a.get(k) != tips_b.get(k)
    ]
    known = {"rekvizit_document", "tasks", "tekshirish_kerak", "takliflar"}
    if any(a.get(k) != b.get(k) for k in (set(a) | set(b)) - known):
        changed.append("boshqa")
    return changed


def compare(first: str, second: str) -> None:
    left, right = OUT_DIR / first, OUT_DIR / second
    for folder in (left, right):
        if not any(folder.glob("*.json")):
            print(f"{folder}/ da javob yo'q — avval: measure_time <papka> --name {folder.name}")
            return
    ids = sorted({p.stem for p in left.glob("*.json")} | {p.stem for p in right.glob("*.json")})
    same, differ, missing = 0, [], []
    for doc_id in ids:
        a, b = left / f"{doc_id}.json", right / f"{doc_id}.json"
        if not (a.exists() and b.exists()):
            missing.append(doc_id)
            continue
        fields = changed_fields(json.loads(a.read_text("utf-8")), json.loads(b.read_text("utf-8")))
        if fields:
            differ.append((doc_id, fields))
        else:
            same += 1
    print(f"Javoblar: {first} va {second} — {len(ids)} xat")
    print(
        f"  AYNAN bir xil: {same}, farq qildi: {len(differ)}, faqat bittasida bor: {len(missing)}"
    )
    for doc_id, fields in differ:
        print(f"    {doc_id}: {', '.join(fields)}")
    if missing:
        print(f"    faqat bittasida: {', '.join(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bitta xat vaqti bosqichlar bo'yicha")
    parser.add_argument("folder", type=Path, nargs="?", help="xatlar papkasi (DOC_xxx/{pdf,json})")
    parser.add_argument("--name", default="oldin", help="javoblar papkasi: outputs/vaqt/<nom>")
    parser.add_argument("--limit", type=int, help="faqat birinchi N xat")
    parser.add_argument("--compare", nargs=2, metavar=("BIRINCHI", "IKKINCHI"))
    parser.add_argument(
        "--sequential", action="store_true", help="OCR'lar eskicha — bitta navbatda (solishtirish)"
    )
    args = parser.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    if args.folder is None:
        parser.error("papka kerak (yoki --compare)")
    rows = measure(args.folder, args.name, args.limit, args.sequential)
    report(rows, args.folder, args.name)


if __name__ == "__main__":
    main()
