"""B5.1b: jo'natuvchini blank bo'yicha topish — dev'da leave-one-out. Ekranga FAQAT sonlar.

Har dev xati uchun qolgan 69 ta xat ichidan blanki eng o'xshashi topiladi; uning jo'natuvchisi
to'g'ri kelsa — to'g'ri. 2 usul x 3 blank qismi solishtiriladi, eng yaxshisi uchun esa
o'xshashlik chegarasi (pastda — "tekshirish kerak") jadvali chiqadi. Matn keshdan olinadi.

Ishga tushirish: poetry run python -m scripts.rekvizit.measure_sender_match
"""

from collections import Counter

from scripts.rekvizit.measure_senders import sender_of
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import HEADER_MODES, METHODS, SENDER_THRESHOLD, Matcher, header_text, prune

THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
# Nomzodlar (TF-IDF): (blank qismi, "kamida N xatda" filtri).
# B5.1b: page + filtr 2 tanlangan edi. B5.1c: xodim tasdiqlagan BITTA xat uchun filtr ishlamaydi,
# shuning uchun xotiraga faqat blank ("full": "№" qatoridan yuqori) yoziladi — unda fuqaro ismi yo'q
CANDIDATES = [("page", 1), ("page", 2), ("full", 1)]
CHOSEN = ("full", "tfidf", 1)


def leave_one_out(
    texts: list[str], names: list[str], method: str, min_df: int = 1
) -> list[tuple[bool, float]]:
    """Har xat uchun: (to'g'ri topildimi, o'xshashlik). Model har safar qolgan xatlardan
    qaytadan quriladi — so'z og'irliklariga tekshirilayotgan xatning o'zi ta'sir qilmaydi."""
    result = []
    for i, text in enumerate(texts):
        others = [t for j, t in enumerate(texts) if j != i]
        other_names = [n for j, n in enumerate(names) if j != i]
        reference = prune(others, min_df) if method == "tfidf" else others
        name, score = Matcher(reference, other_names, method).best(text)
        result.append((normalize(name) == normalize(names[i]), score))
    return result


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    pages = [get_pages(letters[doc_id]) for doc_id in dev]
    names = [sender_of(load_truth(letters[doc_id])) for doc_id in dev]
    keys = Counter(normalize(n) for n in names)
    familiar = [keys[normalize(n)] > 1 for n in names]  # jo'natuvchi boshqa dev xatida ham bor
    n, n_fam = len(names), sum(familiar)

    print(f"B5.1b: jo'natuvchini blank bo'yicha topish, dev {n} xat (leave-one-out)")
    print(f"  tanish jo'natuvchili xatlar: {n_fam} — bu usul uchun yuqori chegara\n")
    print(f"  {'blank qismi':<12}{'usul':<8}{'to`g`ri':>14}{'tanishlar ichida':>20}")
    results = {}
    for mode in HEADER_MODES:
        texts = [header_text(p, mode) for p in pages]
        for method in METHODS:
            res = leave_one_out(texts, names, method)
            results[(mode, method)] = res
            ok = sum(c for c, _ in res)
            ok_fam = sum(c for (c, _), f in zip(res, familiar, strict=True) if f)
            share, share_fam = f"({ok / n:4.0%})", f"({ok_fam / n_fam:4.0%})"
            print(f"  {mode:<12}{method:<8}{ok:>6} {share}{ok_fam:>11}/{n_fam} {share_fam}")

    for mode, min_df in CANDIDATES:
        texts = [header_text(p, mode) for p in pages]
        res = leave_one_out(texts, names, "tfidf", min_df)
        ok = sum(c for c, _ in res)
        sure = [c for c, score in res if score >= SENDER_THRESHOLD]
        print(
            f"\n  {mode} + tfidf, so'z kamida {min_df} xatda: to'g'ri {ok}/{n}, "
            f"chegara {SENDER_THRESHOLD} da javob {len(sure)}, to'g'ri {sum(sure)}"
        )
        results[(mode, "tfidf", min_df)] = res
    best = CHOSEN
    print(f"\n  Tanlangan: {best[0]} + {best[1]}, so'z kamida {best[2]} xatda. Chegara bo'yicha:")
    print(f"    {'chegara':<9}{'javob berdi':>14}{'to`g`ri':>10}{'ishonchlilik':>15}")
    for t in THRESHOLDS:
        answered = [c for c, score in results[best] if score >= t]
        ok = sum(answered)
        reliability = f"{ok / len(answered):4.0%}" if answered else "   —"
        print(f"    >= {t:<6}{len(answered):>8} ({len(answered) / n:4.0%}){ok:>6}{reliability:>13}")


if __name__ == "__main__":
    main()
