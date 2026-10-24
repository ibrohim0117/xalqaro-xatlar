"""scripts/ocr/fit_numbers.py testlari — to'qilgan xatlar bilan."""

import json
import sys
from types import SimpleNamespace

from scripts.ocr import fit_numbers
from scripts.ocr.fit_numbers import templates


def truth(sender, number):
    return {"hujjat_junatuvchi_tashkilot": sender, "hujjat_raqami": number}


TRUTHS = {
    "DOC_1": truth("Rossiya, Nijniy Novgorod", "54/07-16606/25"),
    "DOC_2": truth("Rossiya, Nijniy Novgorod", "54/07-17001/25"),
    "DOC_3": truth("Rossiya, Nijniy Novgorod", "54/07-9912/25"),  # tartib raqami qisqaroq
    "DOC_4": truth("Belarus, Minsk", "01-12/345"),
}


def test_template_comes_only_from_other_letters():
    learned = templates(TRUTHS)
    assert learned["DOC_1"].prefix == "54/07-"  # DOC_2 va DOC_3 dan
    assert learned["DOC_4"] is None  # tashkilotning boshqa xati yo'q


def test_main_counts_fixed_and_broken(tmp_path, monkeypatch, capsys):
    saved = {  # VLM aniq savol: DOC_1 bosh qismi xato, DOC_2 to'g'ri
        "DOC_1": {"header": '{"sana": null, "raqam": "34/07-16606/25"}'},
        "DOC_2": {"header": '{"sana": null, "raqam": "54/07-17001/25"}'},
    }
    (tmp_path / "vlm-extract.json").write_text(json.dumps(saved))
    monkeypatch.setattr(fit_numbers, "OUT_DIR", tmp_path)
    monkeypatch.setattr(
        fit_numbers, "list_letters", lambda: [SimpleNamespace(doc_id=d) for d in TRUTHS]
    )
    monkeypatch.setattr(fit_numbers, "load_split", lambda: {"dev": list(TRUTHS)})
    monkeypatch.setattr(
        fit_numbers, "load_truth", lambda letter: {"rekvizit_document": TRUTHS[letter.doc_id]}
    )
    monkeypatch.setattr(sys, "argv", ["fit_numbers", "--show-ids"])
    fit_numbers.main()

    out = capsys.readouterr().out
    assert "header          2      1      2          1        0" in out
    assert "header tuzatildi (1): DOC_1" in out
    assert "oldin 1, qolip bilan 2" in out
    assert "54/07" not in out  # ekranga raqam qiymati chiqmaydi
