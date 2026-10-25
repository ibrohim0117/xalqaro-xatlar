"""B5.9: imzo — hozirgi qoida (signer.find_signer) xato yozgan va yozmagan xatlar turi.

Xato yozilganlar: ijrochi olinganmi ("Исп. А.Р. Фамилия" — imzodan pastda turadi, qoida esa eng
pastdagini oladi), boshqa odammi (to'g'ri familiya matnda bormi), faqat bosh harf farqmi.
Yozilmaganlar: json'dagi familiya 1–6-sahifa matnida bormi (lotinga o'girib, o'xshashlik >= 85 —
measure_signers kabi); bor bo'lsa — qaysi sahifada, sahifaning qaysi qismida va qanday shaklda
("И.О. Фамилия", "Фамилия И.О.", "Имя Фамилия" — to'liq ism, boshqa).
Qo'shimcha (B5.9, 2-o'lchov): xato yozilganda — qaysi qoida topgan ("И.О." yoki "Имя ФАМИЛИЯ"),
to'g'risi qayerda, bosh harflar to'g'ri bo'lsa familiya o'girishidagi farq; yolg'iz familiyada —
oldingi so'z nima (kichik harfli so'z, belgi, lotin) va xatning boshqa joyida shu familiya bosh
harflar bilan uchraydimi (json bilan mosmi); json shakli boshqa bo'lsa — shakli ("Aa A.A.") va
biz nimadir yozdikmi.
3-o'lchov: so'zlar tuzilishi harfsiz (mask: "А.Б." -> "К.К.", "Rustam" -> "Ll"); "Имя ФАМИЛИЯ"
xatosida bizning nomzod qatori va to'g'risiga nisbatan joyi; zaxira qoida (1-sahifada nomzod
yo'q bo'lsa — 2- yoki 2–3-sahifadan) qancha to'g'ri va qancha XATO qo'shishi.
Tanish (B5.9): to_latin ukraincha (і, ї, є, ґ) va turkmancha lotin (ý, ş, ç, ň, ä, ö, ü, ž, w)
harflarini o'girmaydi, katta harfli familiya ("СИДОРОВ") ham matching'dan tushib qolardi — bu
yerda hammasi hisobga olinadi (token_latin). Bosh harf farqi — soni (1 va 2) yoki o'girish
(harf bo'laklari).
Ekranga FAQAT sonlar, turlar, harf bo'laklari va DOC raqamlari (ismlar emas).

Ishga tushirish: poetry run python -m scripts.rekvizit.explain_signers
"""

import re
from collections import defaultdict

from rapidfuzz import fuzz

from scripts.rekvizit.measure_signers import EDGE, translit_diffs
from src.common.text import normalize, to_latin
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.signer import (
    GLUED,
    candidates,
    choose_signer,
    find_signer,
    format_signer,
    initial_latin,
    initials_before,
    parse_json_signer,
)

PAGES = 6
# zaxira qoida variantlari: (oxirgi sahifa, min_y) — faqat 1-sahifada nomzod bo'lmasa
FALLBACKS = {
    "2-sahifa, past": (2, 0.5),
    "2-sahifa, hammasi": (2, 0.0),
    "2–3-sahifa, past": (3, 0.5),
}
UKRAINIAN = str.maketrans(
    {"і": "и", "І": "И", "ї": "йи", "Ї": "Йи", "є": "е", "Є": "Е", "ґ": "г", "Ґ": "Г"}
)
TURKMEN = str.maketrans(
    {
        "ý": "y",
        "Ý": "Y",
        "ş": "sh",
        "Ş": "Sh",
        "ç": "ch",
        "Ç": "Ch",
        "ň": "n",
        "Ň": "N",
        "ä": "a",
        "Ä": "A",
        "ö": "o",
        "Ö": "O",
        "ü": "u",
        "Ü": "U",
        "ž": "j",
        "Ž": "J",
        "w": "v",
        "W": "V",
    }
)
CYRILLIC = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґЎўҚқҒғҲҳ]")
EXECUTOR = re.compile(r"^(?:исп|исполн|вик|ijrochi)", re.IGNORECASE)  # "Исп.", "Исполнитель"


INITIALS_ANY = re.compile(r"^(?:[А-ЯЁІЇЄҐЎҚҒҲA-Z][а-яa-z]?\.){1,3},?$")  # "А.Б.", "І.", "Ш.А."
CAPS = re.compile(r"^[А-ЯЁІЇЄҐЎҚҒҲ'-]{2,}$")
NAME = re.compile(r"^[А-ЯЁІЇЄҐЎҚҒҲ][а-яёіїєґўқғҳ'-]+$")


def word_kind(token: str) -> str:
    """So'z turi (qiymati emas): bosh harflar, Ism, ISM (katta harf), boshqa."""
    word = EDGE.sub("", token) if not INITIALS_ANY.match(token.strip()) else token.strip()
    if INITIALS_ANY.match(word):
        return "И.О."
    if CAPS.match(word):
        return "ИМЯ"
    if NAME.match(word):
        return "Имя"
    return "-"


def shape_at(words, i: int) -> str:
    """Familiya atrofi, so'z turlari bilan: "<oldingi> <familiya> <keyingi> <undan keyingi>"
    ("И.О. Фамилия - -", "Имя ФАМИЛИЯ - -", "Фамилия Имя Имя -"). Faqat shu qatordagi so'zlar."""
    line = words[i].line

    def kind(j: int) -> str:
        return word_kind(words[j].text) if 0 <= j < len(words) and words[j].line == line else "-"

    surname = "ФАМИЛИЯ" if CAPS.match(EDGE.sub("", words[i].text)) else "Фамилия"
    return f"{kind(i - 1)} {surname} {kind(i + 1)} {kind(i + 2)}"


def token_latin(token: str) -> str | None:
    """So'z lotinda, kichik harf: kirill (rus, ukrain, o'zbek; katta harfli ham) — to_latin;
    lotin (turkmancha harflar bilan) — o'zbekcha lotinga. Harfi 3 tadan kam — None."""
    word = EDGE.sub("", token)
    if len(re.findall(r"[^\W\d_]", word)) < 3:
        return None
    if CYRILLIC.search(word):
        return to_latin(word.translate(UKRAINIAN).capitalize()).lower()
    return word.translate(TURKMEN).lower()


def mask(token: str) -> str:
    """So'z tuzilishi, harflarsiz: kirill К/к, lotin L/l, boshqa yozuv harfi ?, raqam 9; kichik
    harflar ketma-ketligi bitta belgi, katta harflar 2 tagacha: "А.Б." -> "К.К.", "Rustam" -> "Ll",
    "СИДОРОВ" -> "КК". Ism ko'rinmaydi, faqat tuzilishi."""
    out: list[str] = []
    for ch in token.strip():
        if CYRILLIC.match(ch):
            c = "К" if ch.isupper() else "к"
        elif "a" <= ch.lower() <= "z":
            c = "L" if ch.isupper() else "l"
        elif ch.isalpha():
            c = "?"
        elif ch.isdigit():
            c = "9"
        else:
            c = ch
        if out and c == out[-1] and (c in "кl9?" or out[-2:] == [c, c]):
            continue
        out.append(c)
    return "".join(out)


def word_detail(token: str) -> str:
    """ "-" turdagi so'z nima (qiymati emas): belgi, raqam, lotin, kichik harfli so'z, boshqa."""
    letters = re.findall(r"[^\W\d_]", token)
    if not letters:
        return "raqam" if re.search(r"\d", token) else "belgi"
    if not CYRILLIC.search(token):
        return "lotin"
    return "kichik harfli so'z" if letters[0].islower() else "boshqa"


def occurrences(pages, surname: str) -> list[tuple[int, list, int]]:
    """Familiya uchragan barcha joylar (1–6-sahifa): (sahifa raqami, sahifa so'zlari, o'rni)."""
    found = []
    for page in pages[:PAGES]:
        words = page.main.words
        for i, word in enumerate(words):
            latin = token_latin(word.text)
            if latin and fuzz.ratio(latin, surname.lower()) >= 85:
                found.append((page.number, words, i))
    return found


def where_in_text(pages, surname: str) -> tuple[int, str, str] | None:
    """Familiya oxirgi uchragan joy (imzo xat oxirida): (sahifa, joyi, shakli)."""
    found = occurrences(pages, surname)
    if not found:
        return None
    number, words, i = found[-1]
    word = words[i]
    side = "o'ng" if word.x0 >= 0.5 else "chap"
    half = "past" if word.y0 >= 0.5 else "yuqori"
    shape = shape_at(words, i)
    if shape.startswith("- ") and i > 0:  # yolg'iz familiya: oldingi so'z nima va qayerda
        prev = words[i - 1]
        kind = word_kind(prev.text)
        kind = word_detail(prev.text) if kind == "-" else kind
        above = "yuqorida" if prev.y0 < word.y0 - 0.005 else "yonida"
        shape += (
            f" [oldingi so'z: {kind} '{mask(prev.text)}', {above}; familiya '{mask(word.text)}']"
        )
    return number, f"{side}-{half}", shape


def initials_near(words, i: int) -> list[str] | None:
    """Familiya yonidagi (shu qatordagi) bosh harflar, lotinda: avval "И.О." (oldin yoki keyin),
    keyin to'liq ism ("Имя Отчество Фамилия", "Фамилия Имя Отчество"). Topilmasa — None."""
    line = words[i].line

    def at(j: int) -> str | None:
        return words[j].text.strip() if 0 <= j < len(words) and words[j].line == line else None

    for wanted in ("И.О.", "Имя"):
        for step in (-1, 1):
            near = [t for t in (at(i + step), at(i + 2 * step)) if t]
            taken = []
            for token in near:
                if word_kind(token) != wanted:
                    break
                taken.append(token)
            if not taken:
                continue
            if step < 0:
                taken.reverse()
            if wanted == "И.О.":
                return [initial_latin(p) for t in taken for p in re.split(r"[.,]", t) if p]
            return [initial_latin(EDGE.sub("", t)[0]) for t in taken]
    return None


def initials_elsewhere(pages, surname: str, initials: list[str]) -> str:
    """Familiya xatda (1–6-sahifa) bosh harflar bilan uchraydimi va ular json bilan mosmi."""
    seen = [initials_near(words, i) for _, words, i in occurrences(pages, surname)]
    seen = [[x.lower() for x in s] for s in seen if s]
    if not seen:
        return "xatda bosh harfi bilan yo'q"
    want = [x.lower() for x in initials]
    return "xatda bosh harfi bilan bor, json bilan MOS" if want in seen else "xatda bor, mos emas"


def json_shape(value: str | None) -> str:
    """json qiymatining shakli (qiymat emas): "Aa A.A.", "A.Aa", "bo'sh"."""
    value = (value or "").strip()
    if not value:
        return "bo'sh"
    shape = re.sub(r"[^\W\d_]", lambda m: "A" if m.group().isupper() else "a", value)
    return re.sub(r"a+", "a", shape)


def index_of(words, candidate) -> int:
    """Nomzod familiyasining sahifa so'zlari ichidagi o'rni."""
    return next(j for j, w in enumerate(words) if (w.x0, w.y0) == (candidate.x0, candidate.y0))


def rule_of(pages, candidate) -> str:
    """Nomzodni qaysi qoida topgan: "И.О. Фамилия", B5.9 "Имя ФАМИЛИЯ" yoki yopishgan."""
    words = pages[candidate.page - 1].main.words
    i = index_of(words, candidate)
    if GLUED.fullmatch(EDGE.sub("", words[i].text)):
        return "И.Фамилия (yopishgan)"
    return "И.О." if initials_before(words, i)[0] else "Имя ФАМИЛИЯ"


def before_initials(pages, candidate) -> str:
    """Imzo (bosh harflar + familiya) harfsiz va undan oldingi 3 so'z: shu qatordami, boshqa
    qatordami, balandligi qanchalik farq qiladi — yo'qolgan bosh harf qayerda qolganini ko'rish."""
    words = pages[candidate.page - 1].main.words
    i = index_of(words, candidate)
    start = i if GLUED.fullmatch(EDGE.sub("", words[i].text)) else initials_before(words, i)[1]
    first = words[start]
    near = []
    for w in words[max(0, start - 3) : start]:
        if w.line == first.line:
            where = "shu qator"
        elif abs(w.y0 - first.y0) < 0.01:
            where = "boshqa qator, bir balandlikda"
        else:
            where = "boshqa qator"
        near.append(f"'{mask(w.text)}' ({where})")
    signer = " ".join(mask(w.text) for w in words[start : i + 1])
    return f"imzo '{signer}', oldida: {', '.join(near) or '-'}"


def chosen_vs_right(pages, candidate, surname: str) -> str:
    """Bizning (xato) nomzod: to'g'ri familiyaga nisbatan joyi va qatori harfsiz (8 so'zgacha)."""
    number, words, j = occurrences(pages, surname)[-1]
    right = words[j]
    if number != candidate.page:
        where = "boshqa sahifada"
    elif candidate.y0 > right.y0 + 0.005:
        where = "pastda"
    elif candidate.y0 < right.y0 - 0.005:
        where = "yuqorida"
    else:
        where = "shu qatorda"
    ours = pages[candidate.page - 1].main.words
    line = [w for w in ours if w.line == ours[index_of(ours, candidate)].line]
    side = "o'ng" if candidate.x0 >= 0.5 else "chap"
    masked = " ".join(mask(w.text) for w in line[:8])
    return f"bizniki to'g'risidan {where}, {side}, qatori '{masked}'"


def is_executor(pages, candidate) -> bool:
    """Tanlangan nomzod oldida (o'sha qatorda) "Исп." kabi so'z bormi."""
    words = pages[candidate.page - 1].main.words
    line = [w for w in words if abs(w.y0 - candidate.y0) < 0.01 and w.x0 < candidate.box[0]]
    return any(EXECUTOR.match(w.text) for w in line)


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    kinds = defaultdict(list)
    fallback = defaultdict(list)  # (variant, "to'g'ri" | "XATO") -> DOC raqamlari
    for doc_id in dev:
        doc = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        raw = doc.get("imzolagan_shaxs")
        parsed = parse_json_signer(raw)
        pages = get_pages(letters[doc_id])
        chosen = find_signer(pages)
        expected = normalize(format_signer(*parsed), spaceless=True) if parsed else None
        if chosen is None:  # zaxira qoida: 1-sahifada nomzod yo'q — keyingi sahifalardan
            for label, (last, min_y) in FALLBACKS.items():
                later = [c for c in candidates(pages, last) if c.page >= 2]
                pick = choose_signer(later, min_y=min_y)
                if pick:
                    ok = normalize(pick.latin(), spaceless=True) == expected
                    fallback[label, "to'g'ri" if ok else "XATO"].append(doc_id)
        if parsed is None:
            wrote = "yozdik" if chosen else "yozmadik"
            kinds[f"json shakli boshqa: {json_shape(raw)}, biz {wrote}"].append(doc_id)
            continue
        initials, surname = parsed
        if chosen and normalize(chosen.latin(), spaceless=True) == expected:
            kinds["yozildi to'g'ri"].append(doc_id)
            continue
        place = where_in_text(pages, surname)
        if chosen:
            rule = f"[qoida: {rule_of(pages, chosen)}]"
            *ours, our_surname = chosen.latin().split(".")
            if is_executor(pages, chosen):
                kind = f"XATO: ijrochi (Исп.) olindi {rule}"
            elif fuzz.ratio(our_surname.lower(), surname.lower()) >= 85:
                if len(ours) != len(initials):
                    kind = (
                        f"XATO: bosh harflar soni (json {len(initials)}, bizda {len(ours)}; "
                        f"{before_initials(pages, chosen)})"
                    )
                elif diffs := translit_diffs("".join(ours), "".join(initials)):
                    kind = f"XATO: bosh harf o'girish ({', '.join(diffs)})"
                else:  # bosh harflar to'g'ri — farq familiyaning o'girishida
                    diffs = translit_diffs(our_surname, surname)
                    marks = "".join(ch for ch in "ьъйыёэ" if ch in chosen.surname.lower())
                    kind = (
                        f"XATO: familiya o'girish ({', '.join(diffs) or 'boshqa'}; "
                        f"kirillda: {marks or '-'})"
                    )
                kind += f" {rule}"
            elif place:
                page, spot, shape = place
                kind = (
                    f"XATO: boshqa odam {rule}, to'g'risi: {page}-sahifa, {spot}, {shape}; "
                    f"{chosen_vs_right(pages, chosen, surname)}"
                )
            else:
                kind = f"XATO: boshqa odam {rule}, to'g'risi matnda yo'q"
        elif place is None:
            kind = "yozilmadi: familiya matnda yo'q"
        else:
            page, spot, shape = place
            page_label = f"{page}-sahifa" if page <= 2 else "3+ sahifa"
            elsewhere = initials_elsewhere(pages, surname, initials)
            kind = (
                f"yozilmadi: {page_label}, {spot}, {shape} (json {len(initials)} bosh harf; "
                f"{elsewhere})"
            )
        kinds[kind].append(doc_id)

    print(f'Imzo (dev {len(dev)} xat; qoida: 1-sahifa, o\'ng-past, "И.О. Фамилия")\n')
    for kind in sorted(kinds, key=lambda k: (not k.startswith("yozildi"), k)):
        print(f"  {kind:<56} {len(kinds[kind]):>3}")
    print("\n  Zaxira qoida (1-sahifada nomzod yo'q bo'lsa) — qo'shiladigan javoblar:")
    for label in FALLBACKS:
        ok, bad = fallback[label, "to'g'ri"], fallback[label, "XATO"]
        print(f"    {label:<20} to'g'ri +{len(ok)} ({', '.join(ok)})")
        print(f"    {'':<20} XATO    +{len(bad)} ({', '.join(bad)})")
    print("\n  DOC raqamlari:")
    for kind in sorted(kinds):
        if kind != "yozildi to'g'ri":
            print(f"    {kind} ({len(kinds[kind])}): {', '.join(kinds[kind])}")


if __name__ == "__main__":
    main()
