"""B5.3b-3: sana — bir necha OCR natijasini birlashtirish ("ovoz berish"). OCR qayta ishlatilmaydi.

compare_ocr saqlagan matnlar (outputs/ocr/<OCR>.json) va matn qatlamidagi sana asosida:
  S0  hozirgi: faqat matn qatlami;
  S1  matn qatlami, bo'lmasa 1-OCR'ning date bo'lagi;
  S2  matn qatlami, bo'lmasa date bo'laklaridan kamida 2 OCR kelishgan sana;
  S3  S2 + header'dagi "№" qatori sanasi ham ovozga kiradi (RapidOCR "№" ni "No"/"N" deb o'qiydi);
  S4  S3 + line bo'lagi va header'dagi birinchi sana ham (ko'proq javob, kamroq ishonch);
  S5  1-OCR (masalan VLM) sanasi — date bo'lagi, bo'lmasa header'dagi "№" qatori — faqat kamida
      bitta boshqa OCR shu sanani biror bo'lakda ko'rgan bo'lsa (biri topadi, boshqasi tasdiqlaydi);
  S5a S5, lekin kamida IKKITA boshqa OCR tasdiqlashi kerak;
  S5b S5, lekin tasdiq faqat ishonchli bo'laklardan (date yoki header'dagi "№" qatori).
"jami" — avtomatik to'g'ri + to'g'ri sana 3 taklif ichida (xodim bir bosishda tanlaydi).
--window N: kelgan sanadan (json kirish_sana; real ishda — bugun) oldin va ko'pi bilan N kun oldingi
sanalargina qabul qilinadi — "16.12.2015" kabi xato o'qilgan yil chetlanadi.
Har OCR o'zi topgan sanalar TO'PLAMI bilan bitta ovoz beradi (bir OCR ikki bo'lakdan bir xil sana
o'qisa — bitta ovoz). Avtomatik javob bo'lmagan xatlarga taklif: eng ko'p OCR ko'rgan sana;
"3 ichida" — to'g'ri sana ovoz bo'yicha eng yuqori 3 ta taklif orasidami (xodim tanlaydi).
Ekranga FAQAT sonlar chiqadi; --ids — avtomatik xato bergan xatlarning DOC raqamlari (qiymatlarsiz),
qo'lda tekshirish uchun.

Avval: poetry run python -m scripts.ocr.compare_ocr rapidocr rapidocr-eslav tesseract-block
Keyin: poetry run python -m scripts.ocr.combine_dates rapidocr rapidocr-eslav tesseract-block
"""

import argparse
import json
import statistics
from collections import Counter

from scripts.ocr.compare_ocr import OUT_DIR
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number
from src.fields.date_vote import (
    STRONG,
    confirmed,
    engine_dates,
    in_window,
    ranked,
    to_day,
    vote,
    windowed,
)

S5 = "S5 1-OCR + tasdiq"
S5A = "S5a 1-OCR + 2 tasdiq"
S5B = "S5b 1-OCR + ishonchli tasdiq"
SOURCES = {  # strategiya -> har OCR'dan qaysi sanalar ovozga kiradi
    "S2 date bo'laklari": ("date",),
    "S3 + header '№' qatori": ("date", "header_anchor"),
    "S4 + line, header birinchi": ("date", "header_anchor", "line", "header_first"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readers", nargs="+", help="compare_ocr saqlagan OCR nomlari")
    parser.add_argument("--ids", action="store_true", help="avtomatik xatolarning DOC raqamlari")
    parser.add_argument("--window", type=int, default=None, help="kelgan sanadan ko'pi bilan N kun")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    texts = {
        r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in args.readers
    }
    stats = Counter()  # (strategiya, "auto" | "auto_ok" | "hint" | "hint_ok")
    gaps = []  # kirish_sana - hujjat_sana (kun), json bo'yicha
    wrong: dict[str, list[str]] = {}  # strategiya -> avtomatik xato bergan xatlar
    for doc_id in dev:
        document = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        truth, received = document.get("hujjat_sana"), to_day(document.get("kirish_sana"))
        if received and to_day(truth):
            gaps.append((received - to_day(truth)).days)
        text_layer = date_and_number(get_pages(letters[doc_id])[0].text_layer)[0]
        found = [engine_dates(texts[r].get(doc_id, {})) for r in args.readers]
        if not in_window(text_layer, received, args.window):
            text_layer = None
        found = [
            windowed(f, received, args.window) for f in found
        ]  # oynadan tashqarisi — nomzod emas
        auto = {
            "S0 hozirgi (matn qatlami)": text_layer,
            "S1 + 1-OCR date bo'lagi": text_layer or found[0]["date"],
        }
        for name, keys in SOURCES.items():
            auto[name] = text_layer or vote([{f[k] for k in keys if f[k]} for f in found])
        auto[S5] = text_layer or confirmed(found)
        auto[S5A] = text_layer or confirmed(found, min_others=2)
        auto[S5B] = text_layer or confirmed(found, keys=STRONG)
        everything = [{d for d in f.values() if d} for f in found]
        hint = vote(everything, min_votes=1)
        top3 = ranked(everything)
        for name, value in auto.items():
            if value:
                stats[name, "auto"] += 1
                stats[name, "auto_ok"] += value == truth
                if value != truth:
                    wrong.setdefault(name, []).append(doc_id)
            elif top3:
                stats[name, "hint"] += bool(hint)
                stats[name, "hint_ok"] += hint == truth
                stats[name, "top3_ok"] += truth in top3

    print(f"Sana: OCR'larni birlashtirish, dev {len(dev)} xat; OCR'lar: {', '.join(args.readers)}")
    if gaps:
        window = args.window or "yo'q"
        print(f"  json: kirish_sana - hujjat_sana = {min(gaps)}..{max(gaps)} kun, ", end="")
        print(f"median {statistics.median(gaps):.0f}; oyna: {window}\n")
    head = (
        f"{'avtomatik':>10}{'to`g`ri':>9}{'xato':>6}{'taklif':>9}{'to`g`ri':>9}"
        f"{'3 ichida':>10}{'jami':>7}"
    )
    print(f"  {'strategiya':<30}{head}")
    for name in ["S0 hozirgi (matn qatlami)", "S1 + 1-OCR date bo'lagi", *SOURCES, S5, S5A, S5B]:
        auto_n, ok = stats[name, "auto"], stats[name, "auto_ok"]
        hints = f"{stats[name, 'hint']:>9}{stats[name, 'hint_ok']:>9}{stats[name, 'top3_ok']:>10}"
        hints += f"{ok + stats[name, 'top3_ok']:>7}"
        print(f"  {name:<30}{auto_n:>10}{ok:>9}{auto_n - ok:>6}{hints}")

    if args.ids:
        print("\n  Avtomatik xatolar (DOC raqamlari):")
        for name in (S5, S5A, S5B, "S2 date bo'laklari"):
            print(f"    {name:<30} {', '.join(wrong.get(name, [])) or '—'}")


if __name__ == "__main__":
    main()
