"""src/dataset.py testlari — faqat soxta (to'qilgan) xatlar bilan, real ma'lumotsiz."""

import json
from pathlib import Path

from src.dataset import expected_boshqarma, group_of, list_letters, make_split

VILOYAT = "Farg'ona viloyati adliya boshqarmasi"
NOTARIAT = "Notariat, advokatura va mediatsiya boshqarmasi"
XALQARO = "Xalqaro-huquqiy hamkorlik boshqarmasi"


def truth(boshqarma: str) -> dict:
    """Real json tuzilishini takrorlovchi soxta to'g'ri javob."""
    if boshqarma == VILOYAT:  # viloyat: boshqarma asosiy_ijrochilar'da, bo'lim maydoni bo'sh
        task = {"asosiy_ijrochilar": [VILOYAT], "asosiy_ijrochilar_boshqarmalari": []}
    else:  # ichki bo'lim: ijrochi — xodim, boshqarma alohida maydonda
        task = {
            "asosiy_ijrochilar": ["SOXTA XODIM ISMI"],
            "asosiy_ijrochilar_boshqarmalari": [boshqarma],
        }
    return {"rekvizit_document": {}, "tasks": [task]}


def make_fake_letters(root: Path, counts: dict[str, int]) -> None:
    n = 0
    for boshqarma, count in counts.items():
        for _ in range(count):
            folder = root / f"DOC_{n:04d}"
            folder.mkdir()
            (folder / f"file_{n}.pdf").write_bytes(b"%PDF-soxta")
            (folder / f"Xat_{n}.json").write_text(json.dumps(truth(boshqarma)), encoding="utf-8")
            n += 1


def test_expected_boshqarma_prefers_department_field():
    assert expected_boshqarma(truth(NOTARIAT)) == NOTARIAT
    assert expected_boshqarma(truth(VILOYAT)) == VILOYAT  # bo'lim bo'sh -> asosiy_ijrochilar
    assert expected_boshqarma({"tasks": []}) is None


def test_group_of():
    assert group_of(VILOYAT) == "viloyat"
    assert group_of(NOTARIAT) == "notariat"
    assert group_of(XALQARO) == "xalqaro"
    assert group_of(None) == "noma'lum"


def test_list_letters_skips_incomplete_folders(tmp_path):
    make_fake_letters(tmp_path, {VILOYAT: 2})
    (tmp_path / "DOC_bosh").mkdir()  # pdf va json yo'q
    (tmp_path / "README.txt").write_text("papka emas")
    assert [letter.doc_id for letter in list_letters(tmp_path)] == ["DOC_0000", "DOC_0001"]


def test_split_is_stratified_complete_and_reproducible(tmp_path):
    make_fake_letters(tmp_path, {VILOYAT: 81, NOTARIAT: 16, XALQARO: 3})
    letters = list_letters(tmp_path)
    split = make_split(letters)

    assert len(split["test"]) == 30 and len(split["dev"]) == 70
    assert not set(split["dev"]) & set(split["test"])  # kesishma yo'q
    assert set(split["dev"]) | set(split["test"]) == {x.doc_id for x in letters}  # hammasi bor

    groups = {
        x.doc_id: group_of(expected_boshqarma(json.loads(x.truth.read_text()))) for x in letters
    }
    test_groups = sorted(groups[d] for d in split["test"])
    assert test_groups.count("viloyat") == 24
    assert test_groups.count("notariat") == 5
    assert test_groups.count("xalqaro") == 1  # kichik guruh ham testda ishtirok etadi

    assert make_split(letters) == split  # bir xil seed -> bir xil natija
    assert make_split(letters, seed=7) != split  # boshqa seed -> boshqa natija
