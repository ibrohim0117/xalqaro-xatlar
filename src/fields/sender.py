"""B5.1: jo'natuvchi tashkilot — xat blankini dev'dagi blanklar bilan solishtirish.

Yangi xatning blanki dev xatlarining blanklari bilan solishtiriladi; eng o'xshash xatning
jo'natuvchisi (json'dagi o'zbekcha nom) javob bo'ladi.

TF-IDF: kam uchraydigan so'z ("новосибирской") ko'p uchraydigan so'zdan ("юстиции", "узбекистан")
og'irroq. Rossiya viloyatlari blanklari faqat bitta so'z bilan farq qiladi — oddiy o'xshashlik
ularni deyarli bir xil deydi, TF-IDF esa aynan o'sha so'zga qaraydi.
"""

import math
import re
from collections import Counter

from rapidfuzz import fuzz

from src.common.text import normalize
from src.fields.layout import header_bottom, in_recipient_block
from src.fields.regions import prepare
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText

# Blank qayeridan olinadi: "left" — "№" qatoridan yuqori, o'ng (qabul qiluvchi) blokisiz;
# "full" — "№" qatoridan yuqori, butun kenglik (markazdagi blanklar uchun); "page" — butun 1-sahifa
HEADER_MODES = ("left", "full", "page")
METHODS = ("fuzz", "tfidf")
TOKEN = re.compile(r"[a-zа-яёўқғҳ']{3,}")  # kamida 3 harfli so'zlar (raqamlar va bo'laklar emas)
# B5.1c: xotirada faqat BLANK ("№" qatoridan yuqori, butun kenglik) — unda fuqaro ismi yo'q,
# shuning uchun xodim tasdiqlagan bitta xatni ham filtrsiz saqlash mumkin (qayta aloqa).
# Dev, halol leave-one-out: >= 0.7 da 48 javob, xatosiz (0.6 da 51 javob, 1 xato).
# Avvalgi variant (butun 1-sahifa + "kamida 2 xatda" filtri) 51/51 bergan, lekin yangi
# tashkilotning o'ziga xos so'zlarini filtr tashlab yuboradi — qayta aloqa bilan ishlamaydi.
SENDER_MODE, SENDER_METHOD = "full", "tfidf"
SENDER_THRESHOLD = 0.7
# B5.8: ball chegaradan past, lekin 1-o'rindagi tashkilot 2-o'rindagi BOSHQA tashkilotdan kamida
# SENDER_MARGIN oldinda VA blankdagi hudud/davlat uning nomida bor (sender_variants.same_place) —
# yoziladi, "tekshiring" bilan. Dev (LOO): to'g'ri topilgan tanishlar margini >= 0.12, xato
# topilganlar <= 0.03; notanishlar (1-o'rin doim xato) marginsi 0.23 gacha — ularni joy sharti
# ushlaydi. 0.10 + joy: +3 to'g'ri, 0 xato (0.25 shartsiz ham +3/0, lekin faqat raqamga tayanadi:
# xotirada tashkilot kam bo'lsa Moldova agentligi Gruziya agentligi bilan adashadi — testda bor).
SENDER_MARGIN = 0.10
MIN_DF = 2  # prune() uchun standart qiymat (B5.1b o'lchovida ishlatilgan)


def header_text(pages: list[CachedPage], mode: str = "full") -> str:
    first = pages[0]
    main = first.main
    if mode == "page":
        return main.text
    bottom = header_bottom(first)
    words = [
        w
        for w in main.words
        if w.y0 < bottom and (mode == "full" or not in_recipient_block(w, bottom))
    ]
    return PageText(1, main.source, words).text


def tokens(text: str) -> list[str]:
    return TOKEN.findall(prepare(text))


def blank_words(text: str) -> str:
    """Xotiraga yoziladigan ko'rinish: faqat 3+ harfli so'zlar — telefon, raqam va sanalarsiz."""
    return " ".join(tokens(text))


def prune(texts: list[str], min_df: int = MIN_DF) -> list[str]:
    """Har matndan faqat kamida min_df ta matnda uchragan so'zlar qoladi (bo'shliq bilan ulangan).
    Bitta xatdagina uchraydigan so'zlar (odatda fuqaro ismi, manzili) model fayliga tushmaydi."""
    docs = [tokens(t) for t in texts]
    df = Counter(word for doc in docs for word in set(doc))
    return [" ".join(w for w in doc if df[w] >= min_df) for doc in docs]


class Matcher:
    """Dev xatlari blanklari va jo'natuvchilari; yangi blankka eng o'xshashini topadi."""

    def __init__(self, texts: list[str], names: list[str], method: str = "tfidf"):
        self.names, self.method = names, method
        self.texts = [prepare(t) for t in texts]
        docs = [tokens(t) for t in texts]
        df = Counter(word for doc in docs for word in set(doc))
        n = len(docs)
        # Silliqlangan IDF: hamma xatda uchragan so'z ham 0 emas, lekin eng past og'irlikda
        self.idf = {word: math.log((1 + n) / (1 + count)) + 1 for word, count in df.items()}
        self.vectors = [self._vector(doc) for doc in docs]

    def _vector(self, words: list[str]) -> dict[str, float]:
        counts = Counter(words)
        vec = {w: c * self.idf.get(w, 0.0) for w, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {w: v / norm for w, v in vec.items()}

    def similarity(self, text: str, i: int) -> float:
        """0..1: yangi blank va i-dev xati blanki qanchalik o'xshash."""
        if self.method == "fuzz":
            return fuzz.token_set_ratio(prepare(text), self.texts[i]) / 100
        query = self._vector(tokens(text))
        return sum(v * self.vectors[i].get(w, 0.0) for w, v in query.items())

    def ranked(self, text: str) -> list[tuple[float, str]]:
        """Har tashkilot uchun eng yuqori o'xshashlik (kamayish tartibida): (ball, nom). Bir
        tashkilot nomi turlicha yozilgan bo'lsa ham (katta/kichik harf) — bitta qator."""
        best: dict[str, tuple[float, str]] = {}
        for i, name in enumerate(self.names):
            score, key = self.similarity(text, i), normalize(name)
            if key not in best or score > best[key][0]:
                best[key] = (score, name)
        return sorted(best.values(), key=lambda pair: -pair[0])

    def best(self, text: str, exclude: int | None = None) -> tuple[str | None, float]:
        """(eng o'xshash dev xatining jo'natuvchisi, o'xshashlik). exclude — leave-one-out uchun."""
        scored = [(self.similarity(text, i), i) for i in range(len(self.names)) if i != exclude]
        if not scored:
            return None, 0.0
        score, i = max(scored)
        return self.names[i], score
