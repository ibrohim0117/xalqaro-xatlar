"""Jo'natuvchi va raqam: xotira o'sib borsa, yangi xatlarda qancha yutamiz.

Amalda tizim har tasdiqlangan xatdan o'rganadi: xodim to'g'ri nomni tasdiqlaydi, keyingi xatda u
xotirada bo'ladi (feedback.jsonl). Bu skript shuni taqlid qiladi: yangi 150 xat (data/real2) kelgan
sanasi tartibida o'tkaziladi; har xat FAQAT eski 100 xat va o'zidan OLDIN kelgan yangi xatlar
bilan aniqlanadi. O'zining javobi xotirada yo'q — baho halol.
  A — xotira faqat eski 100 xatdan, o'smaydi (26.10 yakuniy o'lchovdagi holat). Tekshiruv: yakuniy
      125 xatda jo'natuvchi 33 to'g'ri (papka rejimi bilan bir xil) chiqishi kerak.
  B — xotira o'sadi: har xatdan keyin uning to'g'ri nomi, blanki va raqami xotiraga qo'shiladi.
Jo'natuvchi: to'g'ri / xato / yozilmadi va bir bosishda — tashkilot xotirada bor xatlar va xotirada
yo'q (tashkilotning birinchi xati) alohida: birinchi xatni xotira topa olmaydi, faqat takliflar.
Raqam qolipi (OCR'siz): yozilgan jo'natuvchining qolipi bormi va to'g'ri raqam unga mosmi.
Raqam: prototip qoidasi (number_ocr.read_number) measure_time saqlagan OCR matnlaridan — OCR qayta
ishlamaydi. Qatorlar: qolipsiz, A va B qolipi, B* — jo'natuvchi doim to'g'ri (yuqori chegara).
--ids: B dagi muammoli xatlar — jo'natuvchi (xato yoki tanish, lekin yozilmagan): ballar, qaysi
qoida yozgan, belgisi; raqam: qolip natijani o'zgartirgan xatlar. Faqat DOC raqami va sonlar.
Ekranga FAQAT sonlar. Yangi xatlar matni keshga tushadi (outputs/text_cache; birinchi marta sekin).

Ishga tushirish: poetry run python -m scripts.rekvizit.simulate_arrival [--ids]
"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date as Date
from pathlib import Path

from rapidfuzz import fuzz

from scripts.data.sample_new import new_root
from scripts.rekvizit.measure_senders import sender_of
from src.common.text import normalize
from src.engine.date_ocr import DateReading
from src.engine.feedback import with_confirmed
from src.engine.model import Model, learn_model, number_part, number_template
from src.engine.number_ocr import NumberReading, read_number
from src.engine.predict import predict
from src.evaluation.dataset import Letter, list_letters, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_vote import to_day
from src.fields.number_template import key, matches
from src.fields.sender import SENDER_MODE, SENDER_THRESHOLD, Matcher, blank_words, header_text
from src.fields.sender_variants import blank_places, same_place
from src.reading.pages import CachedPage

FIELD = "hujjat_junatuvchi_tashkilot"
FINAL = Path("outputs/papkalar/real2_qolgan125")  # 26.10 yakuniy o'lchov xatlari
# measure_time saqlagan OCR matnlari: yakuniy 125 va yangi 25 (27.10, "sana" nomi bilan)
OCR_DIRS = (Path("outputs/vaqt/yangi125/ocr"), Path("outputs/vaqt/sana/ocr"))
KINDS = ("to'g'ri", "xato", "yozilmadi", "bir bosishda")
TEMPLATE_KINDS = ("qolipga mos", "qolipga mos emas", "qolip yo'q")
SENDER_ROWS = (
    ("A", "xotira o'smaydi (faqat eski 100)"),
    ("B", "xotira o'sadi (har xat tasdiqlanadi)"),
)
NUMBER_ROWS = (
    ("0", "qolipsiz"),
    ("A", "qolip: xotira o'smaydi"),
    ("B", "qolip: xotira o'sadi"),
    ("B*", "B, jo'natuvchi doim to'g'ri bo'lsa"),
)


@dataclass
class Item:
    doc_id: str
    truth: dict
    header: str  # blank matni ("№" qatoridan yuqori) — xotiraga shu yoziladi
    pages: list[CachedPage]

    @property
    def doc(self) -> dict:
        return self.truth.get("rekvizit_document") or {}

    @property
    def sender(self) -> str:
        return sender_of(self.truth)

    @property
    def arrived(self) -> Date | None:
        return to_day(self.doc.get("kirish_sana"))


def same(a: str | None, b: str | None) -> bool:
    return bool(a) and normalize(a) == normalize(b)


def arrival_order(items: list[Item]) -> list[Item]:
    """Kelgan sana tartibida (sanasi yo'q — oxirida); bir kunda kelganlar DOC raqami bo'yicha."""
    return sorted(items, key=lambda item: (item.arrived or Date.max, item.doc_id))


def sender_outcome(answer: dict, truth: str) -> tuple[str, bool]:
    """(to'g'ri / xato / yozilmadi, bir bosishdami — yozilgani to'g'ri yoki takliflarda)."""
    written = answer["rekvizit_document"][FIELD]
    options = answer["takliflar"].get(FIELD) or []
    kind = "yozilmadi" if not written else "to'g'ri" if same(written, truth) else "xato"
    return kind, same(written, truth) or any(same(option, truth) for option in options)


def number_outcome(reading: NumberReading, truth: str | None) -> tuple[str, bool]:
    """Raqam: (to'g'ri / xato / yozilmadi, bir bosishdami); bo'shliqsiz, kichik harf bilan."""

    def right(value: str | None) -> bool:
        return bool(value) and bool(truth) and key(value) == key(truth)

    kind = "yozilmadi" if not reading.prefill else "to'g'ri" if right(reading.prefill) else "xato"
    return kind, right(reading.prefill) or any(right(s) for s in reading.suggestions)


def shown(outcome: tuple[str, bool]) -> str:
    """ "xato (taklifda)" — yozilgani xato yoki yozilmagan, lekin to'g'risi takliflarda."""
    kind, one_click = outcome
    return f"{kind} (taklifda)" if one_click and kind != "to'g'ri" else kind


def template_outcome(model: Model, sender: str | None, number: str | None) -> str:
    """Jo'natuvchining raqam qolipi bormi va to'g'ri raqam unga mosmi."""
    template = number_template(model, sender)
    if template is None:
        return "qolip yo'q"
    return "qolipga mos" if number and matches(number, template) else "qolipga mos emas"


def grown(base: Model, old: list[Item], earlier: list[Item]) -> Model:
    """B xotirasi: eski 100 xat modeli + oldin kelgan yangi xatlar (blank, nom, raqam qolipi)."""
    named = [item for item in earlier if item.sender]
    model = with_confirmed(
        base, [blank_words(item.header) for item in named], [item.sender for item in named]
    )
    return replace(model, number_templates=number_part([item.truth for item in old + earlier]))


def saved_reading(doc_id: str, folders: tuple[Path, ...] = OCR_DIRS) -> DateReading | None:
    """measure_time saqlagan OCR matnlari (ishlagan OCR'lar tartibi bilan); yo'q bo'lsa — None."""
    for folder in folders:
        path = folder / f"{doc_id}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return DateReading(readers=data["readers"], texts=data["texts"])
    return None


def place_status(pages: list[CachedPage], name: str) -> str:
    """Blankdagi joy (hudud/davlat) va tashkilot nomi: mos / boshqa / blankda joy topilmadi."""
    places = blank_places(pages)
    if not places:
        return "joy topilmadi"
    return "joy mos" if same_place(places, name) else "joy boshqa"


def sender_detail(item: Item, model: Model, answer: dict) -> str:
    """Jo'natuvchi qanday tanlangani — faqat sonlar: 1-o'rin balli, 2-o'rindan farqi, joy sharti,
    to'g'ri tashkilot nechanchi o'rinda, qaysi qoida yozgan va "tekshiring" belgisi."""
    ranking = Matcher(model.sender_texts, model.sender_names).ranked(item.header)
    score, top = ranking[0]
    margin = score - (ranking[1][0] if len(ranking) > 1 else 0.0)
    place = place_status(item.pages, top)
    # 1- va 2-o'rin nomlari o'xshashligi (1.00 ga yaqin — bir tashkilot turlicha yozilgan)
    alike = fuzz.ratio(normalize(top), normalize(ranking[1][1])) / 100 if len(ranking) > 1 else 0
    rank = next((i for i, (_, name) in enumerate(ranking, 1) if same(name, item.sender)), None)
    right = f"{rank}-o'rinda ({ranking[rank - 1][0]:.2f})" if rank else "xotirada yo'q"
    written = answer["rekvizit_document"][FIELD]
    rule = "—" if not written else "chegara" if score >= SENDER_THRESHOLD else "farq+joy"
    flag = "bor" if FIELD in answer["tekshirish_kerak"] else "YO'Q"
    return (
        f"1-o'rin {score:.2f}, farq {margin:.2f} (nomlar o'xshashligi {alike:.2f}), {place}; "
        f"to'g'risi {right}; "
        f"yozgan qoida {rule}, belgi {flag}"
    )


def load(letters: list[Letter], label: str) -> list[Item]:
    items = []
    for number, letter in enumerate(letters, 1):
        print(f"\r  {label}: {number}/{len(letters)} xat matni…", end="", flush=True)
        pages = get_pages(letter)
        header = header_text(pages, SENDER_MODE)
        items.append(Item(letter.doc_id, load_truth(letter), header, pages))
    return items


def cells(counter: Counter, keys: tuple[str, ...], n: int) -> str:
    return "".join(f"{counter[k]:>8} {counter[k] / n:>4.0%}" if n else f"{'—':>13}" for k in keys)


def table(counts: Counter, rows: tuple[tuple[str, str], ...], groups: tuple[str, ...]) -> None:
    print(f"  {'':<40}{'xat':>6}" + "".join(f"{k:>13}" for k in KINDS))
    for label, title in rows:
        for group in groups:
            head = f"{label} {title}" if group == "hammasi" else f"    tashkilot {group}"
            count = counts[label, group, "xat"]
            values = Counter({k: counts[label, group, k] for k in KINDS})
            print(f"  {head:<40}{count:>6}{cells(values, KINDS, count)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="B dagi muammoli xatlar (faqat sonlar)")
    args = parser.parse_args()
    old = load(list_letters(), "eski")
    new = arrival_order(load(list_letters(new_root()), "yangi"))
    final = {letter.doc_id for letter in list_letters(FINAL)} if FINAL.exists() else set()
    base = learn_model([item.truth for item in old], [item.header for item in old])
    old_names = {normalize(item.sender) for item in old if item.sender}
    seen = set(old_names)  # B: eski 100 + oldin kelgan yangilar
    senders, numbers = Counter(), Counter()  # (variant, guruh, natija) -> soni
    templates = Counter()  # (variant, natija) -> soni
    final_right = Counter()  # A, yakuniy 125: maydon -> to'g'ri soni
    writes = Counter()  # B yozgan jo'natuvchilar: (belgi, joy holati, to'g'ri/xato) -> soni
    sender_rows, number_rows, no_ocr = [], [], 0
    for i, item in enumerate(new):
        print(f"\r  aniqlash: {i + 1}/{len(new)} xat…" + " " * 10, end="", flush=True)
        name = normalize(item.sender)
        number = item.doc.get("hujjat_raqami")
        model_b = grown(base, old, new[:i])
        written = {}
        for label, model, known in (("A", base, name in old_names), ("B", model_b, name in seen)):
            answer = predict(item.pages, model)
            kind, one_click = sender_outcome(answer, item.sender)
            for group in ("hammasi", "xotirada bor" if known else "xotirada yo'q"):
                senders[label, group, "xat"] += 1
                senders[label, group, kind] += 1
                senders[label, group, "bir bosishda"] += one_click
            written[label] = answer["rekvizit_document"][FIELD]
            templates[label, template_outcome(model, written[label], number)] += 1
            if label == "A" and item.doc_id in final:
                final_right["jo'natuvchi"] += kind == "to'g'ri"
            if label == "B" and written[label]:
                flag = "belgi bilan" if FIELD in answer["tekshirish_kerak"] else "belgisiz"
                writes[flag, place_status(item.pages, written[label]), kind] += 1
            if args.ids and label == "B" and (kind == "xato" or (known and kind == "yozilmadi")):
                group = "tanish" if known else "birinchi xati"
                detail = sender_detail(item, model, answer)
                sender_rows.append(f"{item.doc_id} [{group}, {kind}] {detail}")
        templates["B*", template_outcome(model_b, item.sender, number)] += 1
        seen.add(name)

        reading = saved_reading(item.doc_id)
        if reading is None:
            no_ocr += 1
            continue
        plans = (
            ("0", None),
            ("A", number_template(base, written["A"])),
            ("B", number_template(model_b, written["B"])),
            ("B*", number_template(model_b, item.sender)),
        )
        outcome = {}
        for label, template in plans:
            outcome[label] = number_outcome(read_number(item.pages[0], reading, template), number)
            kind, one_click = outcome[label]
            numbers[label, "hammasi", "xat"] += 1
            numbers[label, "hammasi", kind] += 1
            numbers[label, "hammasi", "bir bosishda"] += one_click
            if label == "A" and item.doc_id in final:
                final_right["raqam"] += kind == "to'g'ri"
        if args.ids and outcome["0"] != outcome["B"]:
            change = f"qolipsiz {shown(outcome['0'])} -> B qolip {shown(outcome['B'])}"
            number_rows.append(f"{item.doc_id}: {change}")

    n = len(new)
    distinct = {normalize(item.sender) for item in new if item.sender}
    print("\r" + " " * 40 + "\r", end="")
    print(f"Jo'natuvchi — yangi {n} xat kelish tartibida; boshlang'ich xotira: eski {len(old)} xat")
    print(f"  (kelgan sanasi yo'q: {sum(item.arrived is None for item in new)} xat)")
    print(
        f"  yangi xatlarda {len(distinct)} xil tashkilot; ulardan eski 100 da bor: "
        f"{len(distinct & old_names)}\n"
    )
    table(senders, SENDER_ROWS, ("hammasi", "xotirada bor", "xotirada yo'q"))
    right = final_right["jo'natuvchi"]
    print(f"\n  Tekshiruv: A, yakuniy {len(final)} xatda to'g'ri {right} (26.10 papka: 33)")

    print("\n  B yozgan jo'natuvchilar: 'tekshiring' belgisi va blankdagi joy bo'yicha")
    right_head = "to'g'ri"
    print(f"  {'':<40}{right_head:>10}{'xato':>8}")
    for flag in ("belgisiz", "belgi bilan"):
        for place in ("joy mos", "joy topilmadi", "joy boshqa"):
            right, wrong = writes[flag, place, "to'g'ri"], writes[flag, place, "xato"]
            if right or wrong:
                print(f"  {flag + ', ' + place:<40}{right:>10}{wrong:>8}")

    print("\nRaqam qolipi (OCR'siz): yozilgan jo'natuvchining qolipi va to'g'ri raqam")
    print(f"  {'':<40}{'xat':>6}" + "".join(f"{k:>18}" for k in TEMPLATE_KINDS))
    for label, title in (*SENDER_ROWS, ("B*", "B, jo'natuvchi doim to'g'ri bo'lsa")):
        values = Counter({k: templates[label, k] for k in TEMPLATE_KINDS})
        line = "".join(f"{values[k]:>13} {values[k] / n:>4.0%}" for k in TEMPLATE_KINDS)
        print(f"  {label + ' ' + title:<40}{n:>6}{line}")

    print("\nRaqam — saqlangan OCR matnlaridan (to'g'ri/xato — '⚠ tekshiring' bilan yozilgani)")
    print(f"  OCR matni saqlanmagan: {no_ocr} xat")
    table(numbers, NUMBER_ROWS, ("hammasi",))
    right = final_right["raqam"]
    print(f"\n  Tekshiruv: A, yakuniy {len(final)} xatda to'g'ri {right} (26.10 papka: 55)")

    if args.ids:
        print("\nB: jo'natuvchi xato yoki tanish, lekin yozilmagan:")
        for row in sender_rows or ["—"]:
            print(f"  {row}")
        print("\nRaqam: qolip (B) natijani o'zgartirgan xatlar:")
        for row in number_rows or ["—"]:
            print(f"  {row}")


if __name__ == "__main__":
    main()
