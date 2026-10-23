"""Real xatlar haqida FAQAT umumiy raqamlar (shaxsiy ma'lumotsiz).

Ekranga hech qachon xat matni, ism, manzil, raqam yoki nom chiqmaydi — faqat sonlar,
foizlar va "shakllar" (harflar A/Я ga, raqamlar 9 ga almashtirilgan tuzilish).
Hech narsa yozilmaydi, faqat o'qiladi.

Ishga tushirish: poetry run python -m scripts.data.profile_data
"""

import json
import re
import statistics
from collections import Counter
from pathlib import Path

import pymupdf

REAL = Path("data/real")
TEXT_LAYER_MIN_CHARS = 50  # sahifada shundan kam belgi bo'lsa — matn qatlami yo'q (skaner)


def shape(value: str | None) -> str:
    """Qiymatning tuzilishi: kirill -> Я, lotin -> A (so'z -> A+), raqam -> 9."""
    if not value:
        return "(bo'sh)"
    value = re.sub(r"[А-Яа-яЁёЎўҚқҒғҲҳІіҢңӘәӨөҮүҰұ]", "Я", value)
    value = re.sub(r"[A-Za-zʻʼ'‘’]", "A", value)
    value = re.sub(r"\d", "9", value)
    # Ketma-ket harflar bitta belgiga qisqaradi: so'z uzunligi ham ko'rinmasin
    return re.sub(r"([AЯ])\1+", r"\1+", value)


def stats(values: list[float]) -> str:
    if not values:
        return "—"
    return f"min {min(values):g} / median {statistics.median(values):g} / max {max(values):g}"


def boshqarma_group(name: str) -> str:
    """Boshqarma nomini faqat guruhga ajratadi (nomning o'zi chiqmaydi)."""
    low = name.lower()
    if "xalqaro" in low:
        return "xalqaro-huquqiy hamkorlik"
    if "notariat" in low:
        return "notariat"
    if "adliya" in low and ("viloyat" in low or "shahar" in low or "qoraqalpog" in low):
        return "hududiy (viloyat/shahar)"
    return "boshqa"


def profile_pdfs(folders: list[Path]) -> None:
    pages, scanned_pdfs, mixed_pdfs, dpis, sizes_mb = [], 0, 0, [], []
    for folder in folders:
        pdf = next(folder.glob("*.pdf"), None)
        if pdf is None:
            continue
        sizes_mb.append(round(pdf.stat().st_size / 1e6, 1))
        doc = pymupdf.open(pdf)
        pages.append(len(doc))
        with_text = sum(len(p.get_text().strip()) >= TEXT_LAYER_MIN_CHARS for p in doc)
        scanned_pdfs += with_text == 0
        mixed_pdfs += 0 < with_text < len(doc)
        first = doc[0]
        for info in first.get_images(full=True)[:1]:
            width_px = info[2]
            dpis.append(round(width_px / (first.rect.width / 72)))
    n = len(pages)
    print(f"PDF fayllar: {n}")
    print(f"  sahifalar: {stats(pages)}, jami {sum(pages)}")
    print(f"  to'liq skaner (matn qatlami yo'q): {scanned_pdfs} ({scanned_pdfs / n:.0%})")
    print(f"  aralash (ba'zi sahifalarda matn bor): {mixed_pdfs}")
    print(f"  matn qatlamli: {n - scanned_pdfs - mixed_pdfs}")
    print(f"  1-sahifa rasmining taxminiy DPI: {stats(dpis)}")
    print(f"  fayl hajmi, MB: {stats(sizes_mb)}")


def profile_jsons(folders: list[Path]) -> None:
    records = []
    for folder in folders:
        path = next(folder.glob("*.json"), None)
        if path:
            records.append(json.loads(path.read_text(encoding="utf-8")))
    print(f"\nJSON fayllar: {len(records)}")

    fields = [
        "hujjat_junatuvchi_tashkilot",
        "hujjat_sana",
        "hujjat_raqami",
        "imzolagan_shaxs",
        "hujjatning_qisqacha_mazmuni",
    ]
    print("  maydon to'ldirilganligi:")
    for field in fields:
        filled = sum(bool((r.get("rekvizit_document") or {}).get(field)) for r in records)
        print(f"    {field:<30} {filled}/{len(records)}")

    summaries = Counter(
        (r["rekvizit_document"].get("hujjatning_qisqacha_mazmuni") or "") for r in records
    )
    print(
        f"  qisqacha mazmun: {len(summaries)} xil qiymat "
        f"(eng ko'p uchragani {summaries.most_common(1)[0][1]} ta xatda)"
    )
    senders = {r["rekvizit_document"].get("hujjat_junatuvchi_tashkilot") for r in records}
    print(f"  jo'natuvchi tashkilotlar: {len(senders)} xil")

    for field in ["hujjat_sana", "hujjat_raqami", "imzolagan_shaxs"]:
        shapes = Counter(shape(r["rekvizit_document"].get(field)) for r in records)
        print(f"  {field} shakllari (eng ko'p 6 tasi, jami {len(shapes)} xil):")
        for s, count in shapes.most_common(6):
            print(f"    {count:>3}  {s}")

    task_counts = Counter(len(r.get("tasks") or []) for r in records)
    print(f"  xatdagi tasklar soni: {dict(sorted(task_counts.items()))}")
    per_task = Counter(
        len(t.get("asosiy_ijrochilar_boshqarmalari") or [])
        for r in records
        for t in r.get("tasks") or []
    )
    print(f"  taskdagi boshqarmalar soni: {dict(sorted(per_task.items()))}")

    names = [
        b
        for r in records
        for t in r.get("tasks") or []
        for b in t.get("asosiy_ijrochilar_boshqarmalari") or []
    ]
    groups = Counter(boshqarma_group(b) for b in names)
    print(f"  boshqarmalar (jami {len(names)} ta, {len(set(names))} xil nom):")
    for group, count in groups.most_common():
        print(f"    {group:<28} {count:>3} ({count / len(names):.0%})")


def main() -> None:
    folders = sorted(p for p in REAL.iterdir() if p.is_dir())
    print(f"Papkalar: {len(folders)}\n")
    profile_pdfs(folders)
    profile_jsons(folders)


if __name__ == "__main__":
    main()
