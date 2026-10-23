// DOM yordamchilari. Xavfsizlik: xatdan o'qilgan matn faqat textContent orqali qo'yiladi (innerHTML
// emas) — OCR matnidagi "<script>" kabi bo'lak kod bo'lib ishlab ketmaydi.

export const $ = (id) => document.getElementById(id);

/** Element yasash: el("div", {className: "x"}, "matn", boshqaElement) — matn har doim textContent. */
export function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
