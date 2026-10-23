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
        (
            "Farg‘ona viloyati, Qo'qon shahri",
            [("fargona", STRONG), ("fargona", PLACE)],
        ),  # o'zbekcha, ‘ apostrof
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


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Асакинский р-н", "andijon"),  # Асака -> Асакинский: o'zak o'zgaradi
        ("Хивинский район", "xorazm"),
        ("Нуратинского района", "navoiy"),
        ("Каршинский район", "qashqadaryo"),
        ("Ферганский район", "fargona"),  # viloyat markazi nomidagi tuman
        ("Самаркандский р-н", "samarqand"),
        ("Бухарского района", "buxoro"),
        ("Сырдарьинский район", "sirdaryo"),
    ],
)
def test_district_adjectives(text, key):
    assert keys(text) == [(key, PLACE)]


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Toshkent shahar Yunusobod tumani FHDYO bo'limi", "toshkent_sh"),  # "shahar" shakli
        ("Тошкент шаҳар Юнусобод тумани ФҲДЁ бўлими", "toshkent_sh"),
        ("Toshkent shahri Mirzo Ulug‘bek tumani", "toshkent_sh"),  # ‘ apostrof
        ("Toshkent tumani FHDYO", "toshkent_v"),  # tuman — viloyatda
        ("Qo'qon shahri", "fargona"),
        ("Navoiy shahri", "navoiy"),
        ("Termiz shahri", "surxondaryo"),
    ],
)
def test_uzbek_forms(text, key):
    assert {k for k, _ in keys(text)} == {key}


@pytest.mark.parametrize("text", ["Alisher Navoiy ko'chasi", "qarshi chiqdi", "Guliston ismli"])
def test_uzbek_lookalikes_are_ignored(text):
    assert keys(text) == []
