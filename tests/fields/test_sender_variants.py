"""src/fields/sender_variants.py testlari — ochiq tashkilot nomlari va to'qilgan blanklar bilan."""

import pytest

from src.fields.sender_variants import (
    blank_places,
    find_country,
    find_region,
    page_variants,
    region_names,
    same_place,
    sender_variants,
)
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word

RECIPIENT = "Агентство государственных услуг при Министерстве юстиции Республики Узбекистан"


@pytest.mark.parametrize(
    ("adjective", "names"),
    [
        ("нижегородской", ["Nijegorod", "Nijegorodsk"]),
        ("ростовской", ["Rostov", "Rostovsk"]),
        ("ставропольского", ["Stavropol", "Stavropolsk"]),  # Ь tushib qoladi
        ("московской", ["Moskva"]),  # noyob — lug'atdan
        ("жамбылской", ["Jambil"]),
    ],
)
def test_region_names(adjective, names):
    assert region_names(adjective) == names


def test_recipient_uzbekistan_is_not_the_sender_country():
    assert find_country("министерство юстиции республики узбекистан") is None


@pytest.mark.parametrize(
    ("blank", "expected"),
    [
        (
            "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ РОССИЙСКОЙ ФЕДЕРАЦИИ ПО НИЖЕГОРОДСКОЙ ОБЛАСТИ",
            "Rossiya Federatsiyasi Adliya vazirligining Nijegorodsk viloyati bo'yicha "
            "bosh boshqarmasi",
        ),
        (
            "Отдел записи актов гражданского состояния Ростовской области",
            "Rostov viloyati FHDY bo'limi",
        ),
        ("Управление ЗАГС Республики Бурятия", "Buryatiya Respublikasi FHDY boshqarmasi"),
        ("УМВД России по Тверской области", "RF IIV Tver viloyati bo'yicha boshqarmasi"),
        ("Министерство юстиции Туркменистана", "Turkmaniston Adliya vazirligi"),
        (
            "Министерство юстиции Грузии Агентство по развитию государственных сервисов",
            "Gruziya Adliya vazirligi",
        ),
    ],
)
def test_staff_name_is_among_variants(blank, expected):
    assert expected in sender_variants(blank + " " + RECIPIENT)  # qabul qiluvchi xalaqit bermaydi


def test_agency_in_recipient_block_is_not_the_sender_family():
    variants = sender_variants("Отдел ЗАГС Ростовской области " + RECIPIENT)
    assert not any("agentligi" in v or "Adliya vazirligi" in v for v in variants)


def test_first_time_foreign_ministry_and_unknown_blank():
    assert sender_variants("Ministerio de Justicia de la República Argentina") == [
        "Argentina Respublikasi Adliya vazirligi"
    ]
    assert sender_variants("Какой-то текст без названия организации") == []
    assert len(sender_variants("ГЛАВНОЕ УПРАВЛЕНИЕ МИНЮСТА РОССИИ ПО РОСТОВСКОЙ ОБЛАСТИ")) <= 4


def test_uzbek_region_in_blank_is_not_the_sender_region():
    blank = "Управление ЗАГС Республики Бурятия. Запрос в отдел ЗАГС Кашкадарьинской области"
    variants = sender_variants(blank)
    assert all(v.startswith("Buryatiya") for v in variants)  # Qashqadaryo emas
    assert "Buryatiya Respublikasi FHDY boshqarmasi" in variants


def test_zags_unit_is_the_word_next_to_zags():
    blank = "Государственный комитет Республики Башкортостан по делам юстиции, отдел ЗАГС"
    assert sender_variants(blank)[0] == "Boshqirdiston Respublikasi FHDY bo'limi"


def test_english_ministry():
    blank = "Ministry of Justice of the People's Republic of China"
    assert sender_variants(blank) == ["Xitoy Xalq Respublikasi Adliya vazirligi"]


def test_ocr_interleaved_columns_are_separated():
    # OCR qatori: chap blok va o'ng (qabul qiluvchi) blok so'zlari aralashgan
    line = [("ГЛАВНОЕ", 0.1), ("УПРАВЛЕНИЕ", 0.2), ("Республики", 0.6), ("Узбекистан", 0.7)]
    line2 = [("МИНИСТЕРСТВА", 0.1), ("ЮСТИЦИИ", 0.25), ("РФ", 0.35)]
    line3 = [("ПО", 0.1), ("НОВОСИБИРСКОЙ", 0.13), ("ОБЛАСТИ", 0.3), ("г.", 0.6), ("Ташкент", 0.65)]
    words = [
        Word(text, x, y, x + 0.05, y + 0.01, k)
        for k, (row, y) in enumerate([(line, 0.1), (line2, 0.12), (line3, 0.14)])
        for text, x in row
    ]
    pages = [CachedPage(1, PageText(1, "ocr", words), None)]
    assert (
        "Rossiya Federatsiyasi Adliya vazirligining Novosibirsk viloyati bo'yicha bosh boshqarmasi"
        in page_variants(pages)
    )


def test_ocr_lost_short_i():
    blank = "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ РОССИЙСКОЙ ФЕДЕРАЦИИ ПО НОВОСИБИРСКОИ ОБЛАСТИ"
    assert (
        "Rossiya Federatsiyasi Adliya vazirligining Novosibirsk viloyati bo'yicha bosh boshqarmasi"
        in sender_variants(blank)
    )  # "Й" -> "И" (skaner OCR xatosi)


def test_moscow_city():
    blank = "Главное управление Министерства юстиции Российской Федерации по Москве"
    assert "RF Adliya vazirligi Moskva bo'yicha bosh boshqarmasi" in sender_variants(blank)


def test_centered_blank_is_read_in_both_orders():
    # Markazdagi blank: "Республики" chap ustunda, "Башкортостан" o'ngda
    row1 = [("Управление", 0.30, 0.1), ("ЗАГС", 0.42, 0.1)]
    row2 = [("Республики", 0.30, 0.12), ("Башкортостан", 0.48, 0.12)]
    words = [
        Word(text, x, y, x + 0.1, y + 0.01, k)
        for k, row in enumerate([row1, row2])
        for text, x, y in row
    ]
    variants = page_variants([CachedPage(1, PageText(1, "text_layer", words), None)])
    assert variants[0] == "Boshqirdiston Respublikasi FHDY bo'limi"


def test_chinese_blank():
    assert sender_variants("中华人民共和国司法部") == ["Xitoy Xalq Respublikasi Adliya vazirligi"]


def blank_page(text: str) -> list[CachedPage]:
    words = [Word(t, 0.1, 0.05, 0.2, 0.06, 0) for t in text.split()]
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


def test_place_of_the_blank_must_be_in_the_known_name():
    novo = blank_places(blank_page("ГЛАВНОЕ УПРАВЛЕНИЕ МИНЮСТА ПО НОВОСИБИРСКОЙ ОБЛАСТИ"))
    assert "Novosibirsk" in novo
    assert same_place(novo, "Rossiya Federatsiyasi Adliya vazirligining Novosibirsk viloyati …")
    moldova = blank_places(blank_page("Министерство юстиции Республики Молдова Агентство"))
    assert moldova == ["Moldova"]
    assert not same_place(moldova, "Gruziya Adliya vazirligi")  # tuzilishi o'xshash, joy boshqa
    assert not same_place([], "Gruziya Adliya vazirligi")  # joy topilmasa — ehtiyot: yo'q


def test_any_republic_is_transliterated():
    blank = "Российская Федерация Республика Калмыкия отдел ЗАГС Управления ЗАГС Калмыкии"
    assert "Kalmikiya Respublikasi FHDY bo'limi" in sender_variants(blank)
    assert find_region("республика калмыкия") == (["Kalmikiya"], "Respublikasi")
    assert find_region("республики коми") == (["Komi"], "Respublikasi")
    assert find_region("республика беларусь") is None  # davlat — alohida (COUNTRIES)
    assert find_region("республиканское государственное учреждение") is None  # sifat, nom emas
