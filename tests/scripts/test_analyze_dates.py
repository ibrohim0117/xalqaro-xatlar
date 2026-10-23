"""scripts/rekvizit/analyze_dates.py testlari — soxta xatlar bilan."""

import json
import sys

from scripts.rekvizit import analyze_dates
from src.evaluation.dataset import Letter
from tests.conftest import FAKE_LETTER, make_letter_pdf
from tests.engine.test_locate import pages_of


def run(tmp_path, monkeypatch, letters: dict[str, tuple[list, str]]) -> None:
    """letters: DOC_id -> (1-sahifa qatorlari, json'dagi sana)."""
    found = []
    for doc_id, (lines, date) in letters.items():
        pdf = make_letter_pdf(tmp_path / f"{doc_id}.pdf", lines)
        truth = tmp_path / f"{doc_id}.json"
        truth.write_text(json.dumps({"rekvizit_document": {"hujjat_sana": date}}))
        found.append(Letter(doc_id, pdf, truth))
    monkeypatch.setattr(analyze_dates, "list_letters", lambda: found)
    monkeypatch.setattr(analyze_dates, "load_split", lambda: {"dev": list(letters), "test": []})
    monkeypatch.setattr(analyze_dates, "get_pages", lambda letter: pages_of(letter.pdf))
    monkeypatch.setattr(sys, "argv", ["analyze_dates", "--ids"])
    analyze_dates.main()


def test_cases_and_places(tmp_path, monkeypatch, capsys):
    no_anchor = [line for line in FAKE_LETTER if "№" not in line[2]]
    in_text = [*no_anchor, (50, 300, "Справка от 01.02.2026 выдана")]  # sana matnda, "от" dan keyin
    run(
        tmp_path,
        monkeypatch,
        {
            "DOC_A": (FAKE_LETTER, "12.03.2026"),  # "№" qatorida bosma — avtomatik to'g'ri
            "DOC_B": (FAKE_LETTER, "13.03.2026"),  # "№" bor, lekin to'g'ri sana boshqa (qo'lda)
            "DOC_C": (in_text, "01.02.2026"),  # "№" yo'q, sana matnda "от" dan keyin
        },
    )
    out = capsys.readouterr().out
    assert "A. avtomatik to'g'ri: 1" in out
    assert "B. '№' bor, sana topilmadi/xato: 1" in out and "DOC_B" in out
    assert "matn qatlami: 'от' dan keyin" in out and "DOC_C" in out


def test_rule_candidates(tmp_path):
    letter = [line for line in FAKE_LETTER if "№" not in line[2]]
    letter += [(50, 110, "№ 55/07-1234 от 12.03.2026"), (50, 650, "Дата рождения 01.01.1990")]
    found = analyze_dates.rules(pages_of(make_letter_pdf(tmp_path / "xat.pdf", letter))[0])
    assert found["R0 '№' qatori, 'от' bo'lsa ham"] == "12.03.2026"  # o'z qatoridagi "от" sanasi
    assert found["R1 sarlavhadagi birinchi sana"] is None  # sarlavhadagi sana "от" dan keyin
    assert found["R2 pastki qismdagi oxirgi sana"] is None  # 1990 — yaroqsiz yil (2000–2030)
    assert found["R3 sahifadagi yagona sana"] is None
