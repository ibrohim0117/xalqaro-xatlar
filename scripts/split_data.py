"""B1: real xatlarni dev (70%) va test (30%) ga bo'lish, har guruh o'z ulushiga qarab.

Ekranga FAQAT sonlar chiqadi. Natija data/real/split.json ga yoziladi (gitignore'da).
Bo'linish allaqachon bo'lsa, qayta yozilmaydi — test to'plami o'zgarmasligi kerak.

Ishga tushirish: poetry run python -m scripts.split_data
"""

import json
from collections import Counter

from src.dataset import (
    SPLIT_FILE,
    expected_boshqarma,
    group_of,
    list_letters,
    load_truth,
    make_split,
)


def main() -> None:
    letters = list_letters()
    if SPLIT_FILE.exists():
        print(f"Bo'linish allaqachon bor ({SPLIT_FILE}), qayta yozilmadi.")
        split = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    else:
        split = make_split(letters)
        SPLIT_FILE.write_text(json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Bo'linish yozildi: {SPLIT_FILE}")

    groups = {letter.doc_id: group_of(expected_boshqarma(load_truth(letter))) for letter in letters}
    print(f"\nJami xatlar: {len(letters)} | seed: {split['seed']}")
    for part in ("dev", "test"):
        counts = Counter(groups[doc_id] for doc_id in split[part])
        print(f"  {part:<5} {len(split[part]):>3} ta  {dict(sorted(counts.items()))}")

    overlap = set(split["dev"]) & set(split["test"])
    missing = set(groups) - set(split["dev"]) - set(split["test"])
    print(
        f"\nTekshiruv: dev va test kesishmasi {len(overlap)} ta, "
        f"hech qayerga tushmagan {len(missing)} ta (ikkalasi ham 0 bo'lishi kerak)"
    )


if __name__ == "__main__":
    main()
