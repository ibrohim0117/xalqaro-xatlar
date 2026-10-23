"""B4: xat matnidan boshqarmani aniqlash.

B4.2 — hudud. 1-sahifaning o'ng yuqori bloki (qabul qiluvchi) va qolgan matn alohida qidiriladi:
- o'ng blok butunlay chetga olinadi (dev: 48/57 to'g'ri). "Faqat Toshkentni chetlash" ham sinaldi
  (xat viloyat organiga yozilgan bo'lishi mumkin degan gipoteza) — 47/57, yaxshilamadi;
- qolgan matnda vazirlik manzili ("юстиции Республики Узбекистан", "Сайилгох") yonidagi
  Toshkent hisobga olinmaydi.
Hudud eslatmalari og'irligi bo'yicha eng kuchlisi tanlanadi.
"""

import re
from collections import defaultdict
from dataclasses import replace

from src.pdf_text import PageText, Word
from src.regions import Hit, find_regions, prepare
from src.text_cache import CachedPage

RIGHT_BLOCK_X = 0.45  # o'ng yarmi: qabul qiluvchi bloki shu yerda
HEADER_FALLBACK_Y = 0.40  # "№" topilmasa — sarlavha shu balandlikkacha deb olinadi
ANCHOR_MARGIN = 0.03  # "№" qatoridan biroz pastgacha
MINISTRY = re.compile(r"юстиции\s+республики\s+узбекистан")
# Vazirlik (Sayilgoh, 5) va Davlat xizmatlari agentligi (Amir Temur, 16A) manzillari
MINISTRY_STREET = re.compile(r"са[йи]{1,2}лго[хx]|темура,?\s*16")
# O'ng blok bilan nima qilinadi: "keep" — hisobga olinadi, "drop" — butunlay chiqariladi
# (asosiy qoida), "tashkent" — faqat Toshkent shahri chiqariladi (sinalgan, yaxshilamadi)
RECIPIENT_MODES = ("keep", "drop", "tashkent")
# Rahbar: "asosiy ma'lumot 1–2-sahifada, aniqlik uchun 1–4 olsa ham bo'ladi, qolgani ilova".
# Dev (hudud, 57 xat): 1–2-sahifa 35, 1–4-sahifa 47, hamma sahifa 48 to'g'ri. Tanlandi 1–6 (zaxira).
REGION_PAGES = 6


def header_bottom(first: CachedPage) -> float:
    """Sarlavha qayergacha: eng yuqoridagi "№" (sana-raqam qatori) dan biroz pastgacha.
    "№" ni OCR yaxshiroq topadi, shuning uchun ikkala manbaga ham qaraladi."""
    words = first.text_layer.words + (first.ocr.words if first.ocr else [])
    ys = [w.y0 for w in words if "№" in w.text and w.y0 < 0.5]
    return min(ys) + ANCHOR_MARGIN if ys else HEADER_FALLBACK_Y


def in_recipient_block(word: Word, bottom: float) -> bool:
    return word.x0 >= RIGHT_BLOCK_X and word.y0 < bottom


def recipient_and_body(pages: list[CachedPage], max_pages: int | None = None) -> tuple[str, str]:
    """(qabul qiluvchi bloki matni, qolgan matn)."""
    recipient, body = "", []
    for page in pages[:max_pages]:
        main = page.main
        if page.number == 1:
            bottom = header_bottom(page)
            block = [w for w in main.words if in_recipient_block(w, bottom)]
            rest = [w for w in main.words if not in_recipient_block(w, bottom)]
            recipient = PageText(1, main.source, block).text
            main = PageText(1, main.source, rest)
        body.append(main.text)
    return recipient, "\n".join(body)


def is_ministry_address(low: str, hit: Hit) -> bool:
    """Toshkent eslatmasi vazirlikning o'z manzilimi (xat matni ichida kelgan bo'lsa ham)."""
    if hit.key != "toshkent_sh":
        return False
    before = low[max(0, hit.start - 120) : hit.start]
    around = low[max(0, hit.start - 60) : hit.end + 60]
    return bool(MINISTRY.search(before) or MINISTRY_STREET.search(around))


def text_regions(text: str, drop_ministry: bool = True) -> list[Hit]:
    """Oddiy matndagi hudud eslatmalari (vazirlik manzilisiz)."""
    low = prepare(text)
    hits = find_regions(low)
    if drop_ministry:
        hits = [h for h in hits if not is_ministry_address(low, h)]
    return hits


def letter_regions(
    pages: list[CachedPage],
    max_pages: int | None = None,
    recipient_mode: str = "drop",
    drop_ministry: bool = True,
) -> list[Hit]:
    """Xatdagi hudud eslatmalari: avval o'ng blokdagilari, keyin qolgan matndagilari."""
    recipient, body = recipient_and_body(pages, max_pages)
    if recipient_mode == "drop":
        recipient_hits = []
    else:
        recipient_hits = text_regions(recipient, drop_ministry=False)
        if recipient_mode == "tashkent":
            recipient_hits = [h for h in recipient_hits if h.key != "toshkent_sh"]
    # Qolgan matn topilmalari o'ng blokdan keyin keladi deb joylashadi (teng ballda tartib uchun)
    offset = len(prepare(recipient)) + 1
    body_hits = [
        replace(h, start=h.start + offset, end=h.end + offset)
        for h in text_regions(body, drop_ministry)
    ]
    return recipient_hits + body_hits


def choose_region(hits: list[Hit]) -> str | None:
    """Og'irliklar yig'indisi eng katta hudud; teng bo'lsa — matnda birinchi uchragani."""
    if not hits:
        return None
    score: dict[str, int] = defaultdict(int)
    first: dict[str, int] = {}
    for hit in hits:
        score[hit.key] += hit.weight
        first.setdefault(hit.key, hit.start)
    return max(score, key=lambda key: (score[key], -first[key]))


# ── B4.3: notariat ──
# Mavzu xatning asosiy matnida (1–2-sahifa). Hamma sahifada "нотари…" viloyat xatlarida ko'payadi
# (dev: 1/57 -> 4/57): ilovalarda "нотариально заверенная копия" kabi iboralar bor.
NOTARY_PAGES = 2
NOTARY = re.compile(r"нотари|notar")
CERTIFIED_COPY = re.compile(
    r"нотариальн\w*\s+(?:заверен|удостоверен)\w*|(?:заверен|удостоверен)\w*\s+нотариальн\w*"
)
INHERITANCE = re.compile(r"наследств|наследник|наследодател|завещ|имуществ")
# "mention" — "нотари…" uchradi (N1); "no_copies" — "notarius tasdiqlagan nusxa" iborasisiz (N2);
# "inheritance" — "нотари…" va meros so'zi birga (N3)
NOTARY_MODES = ("mention", "no_copies", "inheritance")


def is_notary(pages: list[CachedPage], mode: str = "mention") -> bool:
    """Xat notariat (meros) ishimi: 1–2-sahifa matnida, qabul qiluvchi blokisiz."""
    low = prepare(recipient_and_body(pages, max_pages=NOTARY_PAGES)[1])
    if mode == "no_copies":
        low = CERTIFIED_COPY.sub(" ", low)
    found = bool(NOTARY.search(low))
    if mode == "inheritance":
        return found and bool(INHERITANCE.search(low))
    return found


def predict_group(
    pages: list[CachedPage], notary_mode: str = "mention"
) -> tuple[str | None, str | None]:
    """(guruh, hudud kaliti). Avval notariat, keyin hudud. Ikkalasi ham topilmasa — (None, None):
    "tekshirish kerak". "Hudud yo'q -> xalqaro" qoidasi ataylab qo'llanmaydi: dev'da 2 ta xalqaro
    xat evaziga 5 ta viloyat xatini noto'g'ri yuborardi."""
    if is_notary(pages, notary_mode):
        return "notariat", None
    region = choose_region(letter_regions(pages, max_pages=REGION_PAGES))
    return ("viloyat", region) if region else (None, None)
