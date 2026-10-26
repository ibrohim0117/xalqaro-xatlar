"""B7 (yangi to'plam): model eski 100 xatning HAMMASIDAN — dev 70 + test 30.

Test xatlari qoida tanlash uchun ishlatilmaydi (ikki marta o'lchangan, endi yopiq), lekin ularning
json'idagi bilim — tashkilot blanklari va nomlari, raqam qoliplari, boshqarma nomlari — modelga
qo'shiladi: amalda ham tizim oldin ko'rgan hamma xatdan o'rganadi. Yangi xatlar (data/real2) bu
modelda yo'q — ular ustidagi o'lchov halol.
outputs/model.json ga yoziladi; dev 70 dan qurilgan oldingisi outputs/model_dev70.json ga
ko'chiriladi (run_predict qayta ishga tushirilsa, model.json yana dev 70 dan quriladi).
Test xatlari matni keshga tushadi (outputs/text_cache, gitignore). Ekranga FAQAT sonlar.

Ishga tushirish: poetry run python -m scripts.prototype.build_model_all
"""

from src.engine.model import MODEL_FILE, learn_model, save_model, template_matches
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import SENDER_MODE, header_text

DEV_BACKUP = MODEL_FILE.with_name("model_dev70.json")


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    split = load_split()
    ids = sorted(split["dev"] + split["test"])
    truths, blanks = [], []
    for number, doc_id in enumerate(ids, 1):
        print(f"\r  {number}/{len(ids)} xat…", end="", flush=True)
        truths.append(load_truth(letters[doc_id]))
        blanks.append(header_text(get_pages(letters[doc_id]), SENDER_MODE))
    if MODEL_FILE.exists() and not DEV_BACKUP.exists():
        MODEL_FILE.rename(DEV_BACKUP)
    model = learn_model(truths, blanks)
    save_model(model)
    same, total = template_matches(model)
    print(f"\rModel {len(ids)} ta xatdan (dev {len(split['dev'])} + test {len(split['test'])}):")
    print(f"  {len(model.names)} ta boshqarma nomi")
    print(f"  {len(model.sender_names)} ta xatdan jo'natuvchi namunalari")
    print(f"  {len(model.number_templates)} ta tashkilot uchun raqam qolipi")
    print(f"  {len(model.reply_shapes)} xil bizning raqam shakli")
    print(f"  viloyat nomlaridan shablonga mos: {same}/{total}")
    print(f"Yozildi: {MODEL_FILE} (dev 70 modeli: {DEV_BACKUP})")


if __name__ == "__main__":
    main()
