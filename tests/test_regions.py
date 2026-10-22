"""src/regions.py testlari — to'qilgan manzil va jumlalar bilan."""

import pytest

from src.regions import PLACE, STRONG, WEAK, find_regions, region_of_boshqarma


def keys(text: str) -> list[tuple[str, int]]:
    return [(hit.key, hit.weight) for hit in find_regions(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("проживает: Ферганская обл., Кувасайский р-н", [("fargona", STRONG), ("fargona", PLACE)]),
        ("уроженец Ферганской области Узбекской ССР", [("fargona", STRONG)]),
        ("Республика Каракалпакстан, г. Нукус", [("qoraqalpog", STRONG), ("qoraqalpog", PLACE)]),
        ("Хорезмская область, г. Ургенч", [("xorazm", STRONG), ("xorazm", PLACE)]),
        ("Farg‘ona viloyati, Qo'qon shahri", [("fargona", STRONG)]),  # o'zbekcha, ‘ apostrof
        ("Самаркандская обл., Ургутский район", [("samarqand", STRONG), ("samarqand", PLACE)]),
    ],
)
def test_finds_regions_with_weights(text, expected):
    assert keys(text) == expected


def test_tashkent_city_and_region_are_separated():
    assert keys("г. Ташкент, Чиланзарский район") == [
        ("toshkent_sh", STRONG),
        ("toshkent_sh", PLACE),
    ]
    assert keys("Ташкентская область, г. Чирчик") == [("toshkent_v", STRONG), ("toshkent_v", PLACE)]
    assert keys("Ташкентский район") == [("toshkent_v", STRONG)]  # tuman viloyatda
    assert keys("направлен в Ташкент") == [("toshkent_sh", WEAK)]  # yolg'iz — kuchsiz


@pytest.mark.parametrize(
    "text",
    [
        "ул. Алишера Навои, д. 5",  # ko'cha — shoir nomi
        "пр-т Бухарский",  # ko'cha (shaklni ham tekshiradi)
        "им. Беруни",  # nomidagi
        "гражданка Ширин Каримова",  # ism, shahar emas
        "Каган Борис Ильич",  # familiya
        "Куня-Ургенч, Туркменистан",  # boshqa davlat
        "Ферганская долина",  # vodiy, viloyat emas
    ],
)
def test_streets_names_and_lookalikes_are_ignored(text):
    assert keys(text) == []


def test_region_of_boshqarma_reads_json_names():
    assert region_of_boshqarma("Farg'ona viloyati adliya boshqarmasi") == "fargona"
    assert region_of_boshqarma("Farg‘ona viloyati adliya boshqarmasi") == "fargona"
    assert region_of_boshqarma("Toshkent shahar adliya boshqarmasi") == "toshkent_sh"
    assert region_of_boshqarma("Toshkent viloyati adliya boshqarmasi") == "toshkent_v"
    assert region_of_boshqarma("Notariat, advokatura va mediatsiya boshqarmasi") is None
    assert region_of_boshqarma(None) is None
