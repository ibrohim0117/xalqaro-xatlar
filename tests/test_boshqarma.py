"""src/boshqarma.py testlari — soxta xat (tests/conftest.py) va to'qilgan jumlalar bilan."""

from src.boshqarma import choose_region, letter_regions, region_text
from src.pdf_text import read_text_layer
from src.regions import PLACE, STRONG, Hit
from src.text_cache import CachedPage


def text_layer_pages(pdf) -> list[CachedPage]:
    """OCR'siz: soxta xatda matn qatlami yetarli."""
    return [CachedPage(p.number, p, None) for p in read_text_layer(pdf)]


def test_recipient_block_is_dropped(letter_pdf):
    pages = text_layer_pages(letter_pdf)
    assert "Ташкент" in region_text(pages, drop_recipient=False)
    kept = region_text(pages)
    assert "Ташкент" not in kept  # o'ng yuqori blok chiqarildi
    assert "Ферганская" in kept and "Сидоров" in kept  # xat matni va imzo qoldi
    assert choose_region(letter_regions(kept)) == "fargona"


def test_ministry_address_inside_body_is_ignored():
    text = (
        "направляем в Министерство юстиции Республики Узбекистан (г. Ташкент, ул. Сайилгох, 5) "
        "для вручения гражданину, проживающему: Наманганская обл., г. Чуст"
    )
    assert [h.key for h in letter_regions(text, drop_ministry=False)][0] == "toshkent_sh"
    assert {h.key for h in letter_regions(text)} == {"namangan"}


def test_real_tashkent_address_is_kept():
    text = "проживающему по адресу: г. Ташкент, Юнусабадский район"
    assert choose_region(letter_regions(text)) == "toshkent_sh"


def test_choose_region_by_total_weight_then_first():
    hits = [Hit("andijon", PLACE, 0, 5, ""), Hit("fargona", STRONG, 10, 15, "")]
    assert choose_region(hits) == "fargona"  # 3 > 2
    hits = [Hit("andijon", PLACE, 0, 5, ""), Hit("fargona", PLACE, 10, 15, "")]
    assert choose_region(hits) == "andijon"  # teng — birinchi uchragani
    assert choose_region([]) is None
