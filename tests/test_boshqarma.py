"""src/boshqarma.py testlari — soxta xatlar (tests/conftest.py) va to'qilgan jumlalar bilan."""

from src.boshqarma import choose_region, letter_regions, recipient_and_body, text_regions
from src.pdf_text import read_text_layer
from src.regions import PLACE, STRONG, Hit
from src.text_cache import CachedPage
from tests.conftest import make_letter_pdf

# Xat to'g'ridan-to'g'ri viloyat organiga yozilgan: hudud faqat o'ng blokda
TO_REGIONAL_BODY = [
    (50, 60, "УПРАВЛЕНИЕ ЮСТИЦИИ"),
    (50, 76, "ВЫМЫШЛЕННОЙ ОБЛАСТИ"),
    (50, 110, "12.03.2026 № 55/07-1234"),
    (340, 60, "Управлению юстиции"),
    (340, 76, "Андижанской области"),
    (50, 200, "Просим вручить прилагаемые документы гражданину."),
    (400, 700, "А.Б. Сидоров"),
]


def text_layer_pages(pdf) -> list[CachedPage]:
    """OCR'siz: soxta xatda matn qatlami yetarli."""
    return [CachedPage(p.number, p, None) for p in read_text_layer(pdf)]


def keys(hits: list[Hit]) -> set[str]:
    return {h.key for h in hits}


def test_recipient_block_is_separated(letter_pdf):
    recipient, body = recipient_and_body(text_layer_pages(letter_pdf))
    assert "Ташкент" in recipient and "Ташкент" not in body
    assert "Ферганская" in body and "Сидоров" in body  # xat matni va imzo qoldi


def test_recipient_block_is_dropped(letter_pdf):
    pages = text_layer_pages(letter_pdf)
    assert "toshkent_sh" in keys(letter_regions(pages, recipient_mode="keep"))
    assert keys(letter_regions(pages)) == {"fargona"}
    assert choose_region(letter_regions(pages)) == "fargona"


def test_tashkent_mode_keeps_other_regions_in_recipient_block(tmp_path):
    pages = text_layer_pages(make_letter_pdf(tmp_path / "xat.pdf", TO_REGIONAL_BODY))
    assert choose_region(letter_regions(pages, recipient_mode="tashkent")) == "andijon"
    assert choose_region(letter_regions(pages)) is None  # asosiy qoida: blok butunlay chetda


def test_ministry_address_inside_body_is_ignored():
    text = (
        "направляем в Министерство юстиции Республики Узбекистан (г. Ташкент, ул. Сайилгох, 5) "
        "для вручения гражданину, проживающему: Наманганская обл., г. Чуст"
    )
    assert text_regions(text, drop_ministry=False)[0].key == "toshkent_sh"
    assert keys(text_regions(text)) == {"namangan"}


def test_agency_address_inside_body_is_ignored():
    text = "Агентству государственных услуг (пр. А. Темура, 16А, г. Ташкент). Самаркандская обл."
    assert keys(text_regions(text)) == {"samarqand"}


def test_real_tashkent_address_is_kept():
    text = "проживающему по адресу: г. Ташкент, Юнусабадский район"
    assert choose_region(text_regions(text)) == "toshkent_sh"


def test_choose_region_by_total_weight_then_first():
    hits = [Hit("andijon", PLACE, 0, 5, ""), Hit("fargona", STRONG, 10, 15, "")]
    assert choose_region(hits) == "fargona"  # 3 > 2
    hits = [Hit("andijon", PLACE, 0, 5, ""), Hit("fargona", PLACE, 10, 15, "")]
    assert choose_region(hits) == "andijon"  # teng — birinchi uchragani
    assert choose_region([]) is None
