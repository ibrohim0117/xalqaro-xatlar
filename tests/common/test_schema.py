"""src/common/schema.py testlari — soxta json'lar bilan."""

from src.common.schema import expected_boshqarma, group_of
from tests.evaluation.test_dataset import NOTARIAT, VILOYAT, XALQARO, truth


def test_expected_boshqarma_prefers_department_field():
    assert expected_boshqarma(truth(NOTARIAT)) == NOTARIAT
    assert expected_boshqarma(truth(VILOYAT)) == VILOYAT  # bo'lim bo'sh -> asosiy_ijrochilar
    assert expected_boshqarma({"tasks": []}) is None


def test_group_of():
    assert group_of(VILOYAT) == "viloyat"
    assert group_of(NOTARIAT) == "notariat"
    assert group_of(XALQARO) == "xalqaro"
    assert group_of(None) == "noma'lum"
