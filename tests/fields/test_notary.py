"""B4.3 notariat qoidasi testlari — to'qilgan jumlalar bilan."""

import pytest

from src.fields.boshqarma import is_notary, predict_group
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word


def pages_of(text: str) -> list[CachedPage]:
    """Bitta sahifali soxta xat: so'zlar xat matni joyida (o'ng yuqori blokda emas)."""
    words = [Word(token, 0.1, 0.5, 0.2, 0.51, 0) for token in text.split()]
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


INHERITANCE = "Нотариус просит сообщить о наследственном деле и имуществе наследодателя"
COPY_ONLY = "Просим выдать свидетельство о рождении. Прилагается нотариально заверенная копия"


@pytest.mark.parametrize(
    ("mode", "inheritance", "copy_only"),
    [("mention", True, True), ("no_copies", True, False), ("inheritance", True, False)],
)
def test_notary_modes(mode, inheritance, copy_only):
    assert is_notary(pages_of(INHERITANCE), mode) is inheritance
    assert is_notary(pages_of(COPY_ONLY), mode) is copy_only


def test_predict_group_order():
    assert predict_group(pages_of(INHERITANCE + " Ферганская область")) == ("notariat", None)
    assert predict_group(pages_of("Просим истребовать запись ЗАГС, Ферганская область")) == (
        "viloyat",
        "fargona",
    )
    assert predict_group(pages_of("Просим оказать правовую помощь")) == (None, None)
