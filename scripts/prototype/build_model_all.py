"""B7: prototipning ishchi modeli — HAMMA xatlardan: eski 100 (dev 70 + test 30) va yangi 150.

O'lchovlar tugadi (yopiq to'plam qolmadi), shuning uchun prototip xotirasi ko'rgan hamma xatdan
o'rganadi — amalda ham shunday bo'ladi. Kelish tartibidagi sinovda (simulate_arrival) xotira o'ssa
jo'natuvchi 27% -> 65% bo'lgan. Modelga: tashkilot blanklari va nomlari, raqam qoliplari, boshqarma
nomlari (har hudud uchun eng ko'p uchragani), javob xat shakllari. Tartib: eski 100 DOC raqami
bo'yicha, keyin yangilar kelgan sanasi bo'yicha (simulate_arrival bilan bir xil).
--eski — faqat eski 100 xat (26.10 yakuniy o'lchov modeli; simulate_new_feedback shuni kutadi).
outputs/model.json ga yoziladi; dev 70 dan qurilgani birinchi marta outputs/model_dev70.json ga
ko'chiriladi (run_predict qayta ishga tushirilsa, model.json yana dev 70 dan quriladi).
Oldingi model.json bilan farq: qaysi hudud kalitlari uchun boshqarma nomi o'zgardi yoki qo'shildi
(faqat kalitlar — "fargona", nomlar emas). Ekranga FAQAT sonlar va hudud kalitlari.

Ishga tushirish: poetry run python -m scripts.prototype.build_model_all [--eski]
"""

import argparse
from datetime import date as Date

from scripts.data.sample_new import new_root
from src.common.text import normalize
from src.engine.model import (
    MODEL_FILE,
    Model,
    learn_model,
    load_model,
    save_model,
    template_matches,
)
from src.evaluation.dataset import Letter, list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_vote import to_day
from src.fields.sender import SENDER_MODE, header_text

DEV_BACKUP = MODEL_FILE.with_name("model_dev70.json")


def arrived(letter: Letter) -> Date:
    """Kelgan sana (json'dagi kirish_sana); yo'q bo'lsa — oxirida."""
    document = load_truth(letter).get("rekvizit_document") or {}
    return to_day(document.get("kirish_sana")) or Date.max


def model_letters(with_new: bool) -> list[Letter]:
    """Eski 100 (dev + test, DOC tartibida); with_new — keyin yangi 150 (kelish tartibida)."""
    letters = {letter.doc_id: letter for letter in list_letters()}
    split = load_split()
    old = [letters[doc_id] for doc_id in sorted(split["dev"] + split["test"])]
    if not with_new:
        return old
    new = sorted(list_letters(new_root()), key=lambda letter: (arrived(letter), letter.doc_id))
    return old + new


def name_changes(before: Model, after: Model) -> tuple[list[str], list[str]]:
    """(nomi o'zgargan hudud kalitlari, yangi qo'shilgan kalitlar) — nomlarning o'zi chiqmaydi."""
    changed = [
        k
        for k in after.names
        if k in before.names and normalize(after.names[k]) != normalize(before.names[k])
    ]
    added = [k for k in after.names if k not in before.names]
    return sorted(changed), sorted(added)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eski", action="store_true", help="faqat eski 100 xat (26.10 modeli)")
    args = parser.parse_args()
    letters = model_letters(with_new=not args.eski)
    truths, blanks = [], []
    for number, letter in enumerate(letters, 1):
        print(f"\r  {number}/{len(letters)} xat…", end="", flush=True)
        truths.append(load_truth(letter))
        blanks.append(header_text(get_pages(letter), SENDER_MODE))
    before = load_model() if MODEL_FILE.exists() else None
    if MODEL_FILE.exists() and not DEV_BACKUP.exists():
        MODEL_FILE.rename(DEV_BACKUP)
    model = learn_model(truths, blanks)
    save_model(model)
    same, total = template_matches(model)
    print(f"\rModel {len(letters)} ta xatdan ({'eski 100' if args.eski else 'eski 100 + yangi'}):")
    print(f"  {len(model.names)} ta boshqarma nomi")
    senders = {normalize(name) for name in model.sender_names}
    print(f"  {len(model.sender_names)} ta xatdan jo'natuvchi namunalari ({len(senders)} xil)")
    print(f"  {len(model.number_templates)} ta tashkilot uchun raqam qolipi")
    print(f"  {len(model.reply_shapes)} xil bizning raqam shakli")
    print(f"  viloyat nomlaridan shablonga mos: {same}/{total}")
    if before is not None:
        changed, added = name_changes(before, model)
        print("  Oldingi model.json bilan farq:")
        print(f"    boshqarma nomi o'zgargan hududlar: {', '.join(changed) or '—'}")
        print(f"    yangi qo'shilgan hududlar: {', '.join(added) or '—'}")
        summary = "ha" if before.summary != model.summary else "yo'q"
        print(f"    qisqacha mazmun o'zgardimi: {summary}")
        print(
            f"    jo'natuvchi namunalari: {len(before.sender_names)} -> {len(model.sender_names)}"
        )
    print(f"Yozildi: {MODEL_FILE} (dev 70 modeli: {DEV_BACKUP})")


if __name__ == "__main__":
    main()
