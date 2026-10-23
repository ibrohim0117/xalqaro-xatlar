"""Real xatlar: tasklar va matn qatlami haqida FAQAT umumiy raqamlar (shaxsiy ma'lumotsiz).

Savollar: boshqarma bo'sh bo'lgan tasklarda ijrochi qaysi maydonda va qanday turda yozilgan?
Viloyatlar taqsimoti qanday? PDF matn qatlami qanchalik toza? "ПОВТОРНО" nechta xatda?
Ism, matn, raqam yoki nom ekranga chiqmaydi — faqat turlar, viloyat nomlari va sonlar.

Ishga tushirish: poetry run python -m scripts.data.profile_tasks
"""

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

REAL = Path("data/real")
STANDARD_SUMMARY = "Xalqaro huquqiy yordam yuzasidan"
# Viloyat nomlari ochiq ma'lumot; qiymatda shu kalit so'z bo'lsa, viloyat sanaladi
REGIONS = {
    "Toshkent shahri": ["toshkent shahar", "toshkent shahri"],
    "Toshkent viloyati": ["toshkent viloyat"],
    "Andijon": ["andijon"],
    "Buxoro": ["buxoro"],
    "Farg'ona": ["farg'ona", "fargʻona", "farg‘ona"],
    "Jizzax": ["jizzax"],
    "Xorazm": ["xorazm"],
    "Namangan": ["namangan"],
    "Navoiy": ["navoiy"],
    "Qashqadaryo": ["qashqadaryo"],
    "Samarqand": ["samarqand"],
    "Sirdaryo": ["sirdaryo"],
    "Surxondaryo": ["surxondaryo"],
    "Qoraqalpog'iston": ["qoraqalpog"],
}
# Alohida so'z: "повторное свидетельство" (takroriy guvohnoma) hisobga olinmaydi
POVTORNO_WORD = re.compile(r"(?<![А-Яа-яЁё])повторно(?![А-Яа-яЁё])", re.IGNORECASE)
PERSON = re.compile(r"^[A-ZʻʼO'G‘’]+(?: [A-ZʻʼO'G‘’]+){1,3}$")  # "FAMILIYA ISM OTA" katta harflarda


def kind(value: str) -> str:
    """Qiymatni faqat turiga ajratadi (qiymatning o'zi chiqmaydi)."""
    low = value.lower()
    if PERSON.match(value.strip()):
        return "odam ismi (KATTA harflarda)"
    if "adliya" in low and any(k in low for keys in REGIONS.values() for k in keys):
        return "hududiy adliya boshqarmasi"
    if "boshqarma" in low or "bo'lim" in low or "departament" in low:
        return "ichki bo'linma"
    return "boshqa"


def region_of(value: str) -> str | None:
    low = value.lower()
    for region, keys in REGIONS.items():
        if any(k in low for k in keys):
            return region
    return None


def profile_tasks(records: list[dict]) -> None:
    fields = [
        "asosiy_ijrochilar",
        "asosiy_ijrochilar_boshqarmalari",
        "qushimcha_ijrochilar",
        "qushimcha_ijrochilar_boshqarmalari",
    ]
    groups = {"boshqarmasi BO'SH tasklar": [], "boshqarmasi BOR tasklar": []}
    for r in records:
        for t in r.get("tasks") or []:
            key = (
                "boshqarmasi BOR tasklar"
                if t.get("asosiy_ijrochilar_boshqarmalari")
                else "boshqarmasi BO'SH tasklar"
            )
            groups[key].append(t)

    regions = Counter()
    for title, tasks in groups.items():
        print(f"\n{title}: {len(tasks)}")
        for field in fields:
            values = [v for t in tasks for v in (t.get(field) or [])]
            empty = sum(not t.get(field) for t in tasks)
            kinds = Counter(kind(v) for v in values)
            print(f"  {field:<36} bo'sh: {empty:>3} | qiymat turlari: {dict(kinds)}")
            regions.update(r for v in values if (r := region_of(v)))

    print(f"\nViloyatlar (barcha ijrochi maydonlarida, jami {sum(regions.values())}):")
    for region, count in regions.most_common():
        print(f"  {region:<20} {count}")

    types = Counter(t.get("task_type") for r in records for t in r.get("tasks") or [])
    descriptions = Counter(t.get("description") for r in records for t in r.get("tasks") or [])
    print(
        f"\ntask_type: {len(types)} xil | description: {len(descriptions)} xil, "
        f"eng ko'pi {descriptions.most_common(1)[0][1]} ta"
    )


def profile_summaries(records: list[dict]) -> None:
    other = [
        (r["rekvizit_document"].get("hujjatning_qisqacha_mazmuni") or "")
        for r in records
        if (r["rekvizit_document"].get("hujjatning_qisqacha_mazmuni") or "") != STANDARD_SUMMARY
    ]
    lengths = sorted(len(s) for s in other)
    with_word = sum("xalqaro" in s.lower() for s in other)
    print(f"\nQisqacha mazmun standartdan farqli: {len(other)} ta | uzunligi (belgi): {lengths}")
    print(f"  ulardan 'xalqaro' so'zi borlari: {with_word}")


def profile_text_layer(folders: list[Path]) -> None:
    word_ok, word_all, povtorno, povtorn_any, uzbek_mentions, letters_with_text = 0, 0, 0, 0, 0, 0
    for folder in folders:
        pdf = next(folder.glob("*.pdf"), None)
        if pdf is None:
            continue
        text = "\n".join(p.get_text() for p in pymupdf.open(pdf))
        if len(text.strip()) < 50:
            continue
        letters_with_text += 1
        words = re.findall(r"\S+", text)
        word_all += len(words)
        # "Toza" so'z: faqat harflardan (kirill yoki lotin), ichida raqam/belgi aralashmagan
        word_ok += sum(bool(re.fullmatch(r"[А-Яа-яЁёA-Za-z]+[.,;:]?", w)) for w in words)
        povtorno += bool(POVTORNO_WORD.search(text))
        povtorn_any += bool(re.search(r"повторн", text, re.IGNORECASE))
        uzbek_mentions += bool(re.search(r"узбек|ташкент|uzbek|o'zbek", text, re.IGNORECASE))
    print(f"\nMatn qatlami bor xatlar: {letters_with_text}")
    print(f"  'toza' so'zlar ulushi: {word_ok / max(word_all, 1):.0%} ({word_all} so'zdan)")
    print(f"  'ПОВТОРНО' alohida so'z sifatida: {povtorno}")
    print(f"  'повторн…' so'z ichida ham (taqqoslash uchun): {povtorn_any}")
    print(f"  O'zbekiston/Toshkent eslatilgan xatlar: {uzbek_mentions}")


def target_group(record: dict) -> str:
    """Kutilgan boshqarma guruhi: ichki boshqarma bo'lsa o'sha, bo'lmasa viloyat."""
    task = (record.get("tasks") or [{}])[0]
    names = task.get("asosiy_ijrochilar_boshqarmalari") or []
    if names:
        return "xalqaro" if "xalqaro" in names[0].lower() else "notariat"
    return (
        "viloyat" if any(region_of(v) for v in task.get("asosiy_ijrochilar") or []) else "noma'lum"
    )


def crosstab(folders: list[Path]) -> None:
    table = Counter()
    for folder in folders:
        pdf, js = next(folder.glob("*.pdf"), None), next(folder.glob("*.json"), None)
        if not (pdf and js):
            continue
        text = "\n".join(p.get_text() for p in pymupdf.open(pdf))
        layer = "matn bor" if len(text.strip()) >= 50 else "matn yo'q"
        mark = "ПОВТОРНО bor" if POVTORNO_WORD.search(text) else "ПОВТОРНО yo'q"
        group = target_group(json.loads(js.read_text(encoding="utf-8")))
        table[(group, layer, mark)] += 1
    print("\nKesishma: boshqarma guruhi x matn qatlami x ПОВТОРНО (son):")
    for (group, layer, mark), count in sorted(table.items()):
        print(f"  {group:<10} {layer:<10} {mark:<14} {count}")


def main() -> None:
    folders = sorted(p for p in REAL.iterdir() if p.is_dir())
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for f in folders
        if (p := next(f.glob("*.json"), None))
    ]
    print(f"Xatlar: {len(records)}")
    profile_tasks(records)
    profile_summaries(records)
    profile_text_layer(folders)
    crosstab(folders)


if __name__ == "__main__":
    main()
