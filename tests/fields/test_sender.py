"""src/fields/sender.py testlari — to'qilgan blanklar va soxta xat bilan."""

from src.fields.sender import Matcher, header_text, prune, tokens
from src.reading.pages import CachedPage
from src.reading.pdf_text import read_text_layer

# Rossiya viloyatlari blanklari: faqat bitta so'z farq qiladi (to'qilgan nomlar)
NOVOSIBIRSK = (
    "Главное управление Министерства юстиции Российской Федерации по Новосибирской области"
)
NIZHNY = "Главное управление Министерства юстиции Российской Федерации по Нижегородской области"
GEORGIA = "Министерство юстиции Грузии Агентство по развитию государственных сервисов"
DEV_TEXTS = [NOVOSIBIRSK, NIZHNY, GEORGIA]
DEV_NAMES = ["Soxta Novosibirsk", "Soxta Nijniy", "Soxta Gruziya"]


def test_tokens_skip_numbers_and_short_bits():
    assert tokens("№ 54/07-16606 от 05.12.2025 г. Главное управление") == ["главное", "управление"]


def test_tfidf_picks_the_one_different_word():
    query = "ГУ Минюста России по Новосибирской области направляет поручение"
    matcher = Matcher(DEV_TEXTS, DEV_NAMES, method="tfidf")
    assert matcher.best(query)[0] == "Soxta Novosibirsk"
    # Hamma xatda bor so'z ("юстиции") kam uchraydigan so'zdan ("новосибирской") yengilroq
    assert matcher.idf["юстиции"] < matcher.idf["новосибирской"]


def test_leave_one_out_excludes_itself():
    matcher = Matcher(DEV_TEXTS + [NOVOSIBIRSK], DEV_NAMES + ["Soxta Novosibirsk"])
    name, score = matcher.best(NOVOSIBIRSK, exclude=0)
    assert name == "Soxta Novosibirsk" and score > 0.99  # 3-indeksdagi nusxasi topildi


def test_header_modes(letter_pdf):
    pages = [CachedPage(p.number, p, None) for p in read_text_layer(letter_pdf)]
    left, full, page = (header_text(pages, mode) for mode in ("left", "full", "page"))
    assert "ВЫМЫШЛЕННОЙ" in left and "Узбекистан" not in left  # o'ng blok chetda
    assert "ВЫМЫШЛЕННОЙ" in full and "Узбекистан" in full  # butun kenglik
    assert "Сидоров" in page and "Сидоров" not in full  # imzo faqat butun sahifada


def test_prune_keeps_only_words_shared_by_letters():
    texts = [NOVOSIBIRSK + " Каримову Алишеру", NOVOSIBIRSK + " Сидоровой Анне", GEORGIA]
    kept = prune(texts, min_df=2)
    assert "новосибирской" in kept[0] and "новосибирской" in kept[1]  # tashkilot belgisi qoladi
    assert "каримову" not in kept[0] and "сидоровой" not in kept[1]  # ismlar (1 xatda) tashlanadi
    # Gruziya xatidan faqat umumiy so'z qoldi: "министерство" va "министерства" — boshqa so'zlar
    assert kept[2] == "юстиции"
