"""build_model_all.name_changes testi — to'qilgan nomlar bilan."""

from scripts.prototype.build_model_all import name_changes
from src.engine.model import Model


def test_name_changes_reports_region_keys_only():
    before = Model(names={"fargona": "Soxta A boshqarmasi", "buxoro": "Soxta B"})
    after = Model(names={"fargona": "Soxta A2 boshqarmasi", "buxoro": "soxta b", "xorazm": "C"})
    assert name_changes(before, after) == (["fargona"], ["xorazm"])  # katta-kichik harf — farq emas
