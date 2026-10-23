"""scripts/data/show_text.py himoyasi testi — soxta bo'linish bilan, real ma'lumotsiz."""

import sys

from scripts.data import show_text

FAKE_SPLIT = {"dev": ["DOC_DEV"], "test": ["DOC_TEST"]}


def test_test_letters_are_detected(monkeypatch):
    monkeypatch.setattr(show_text, "load_split", lambda: FAKE_SPLIT)
    assert show_text.is_test_letter("DOC_TEST")
    assert show_text.is_test_letter("data/real/DOC_TEST/xat.pdf")  # yo'l orqali ham
    assert not show_text.is_test_letter("DOC_DEV")
    assert not show_text.is_test_letter("outputs/soxta_xat.pdf")


def test_test_letter_is_refused_without_flag(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(show_text, "load_split", lambda: FAKE_SPLIT)
    monkeypatch.setattr(show_text, "OUT_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["show_text", "DOC_TEST"])
    show_text.main()
    assert "TEST xati" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())  # hech qanday matn yozilmadi
