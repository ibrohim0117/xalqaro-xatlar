// B7.3: bitta xat sahifasi — PDF yuklanadi, AI javobi maydonlarda, har qiymat joyi PDF ustida ramkada.
// Xavfsizlik: xatdan o'qilgan matn DOM'ga faqat textContent orqali qo'yiladi (innerHTML emas) —
// OCR matnidagi "<script>" kabi bo'lak kod bo'lib ishlab ketmaydi.
"use strict";

const FIELDS = [
  { key: "hujjat_junatuvchi_tashkilot", label: "Jo'natuvchi tashkilot", short: "Jo'natuvchi" },
  { key: "hujjat_sana", label: "Hujjat sanasi", short: "Sana" },
  { key: "hujjat_raqami", label: "Hujjat raqami", short: "Raqam" },
  { key: "imzolagan_shaxs", label: "Imzolagan shaxs", short: "Imzo" },
  { key: "hujjatning_qisqacha_mazmuni", label: "Qisqacha mazmun", short: "Mazmun" },
  { key: "boshqarma", label: "Boshqarma (task)", short: "Boshqarma" },
];
const REKVIZIT = FIELDS.map((f) => f.key).filter((k) => k !== "boshqarma");

const $ = (id) => document.getElementById(id);
let answer = null; // oxirgi AI javobi

/** Element yasash: el("div", {className: "x"}, "matn", boshqaElement) — matn har doim textContent. */
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function valueOf(data, key) {
  if (key === "boshqarma") {
    return data.tasks?.[0]?.asosiy_ijrochilar_boshqarmalari?.[0] ?? null;
  }
  return data.rekvizit_document?.[key] ?? null;
}

function suggestionsOf(data, key) {
  const value = data.takliflar?.[key];
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

// ── Yuklash va tahlil ──
async function analyze(event) {
  event.preventDefault();
  const pdf = $("pdf").files[0];
  if (!pdf) return;
  const form = new FormData();
  form.append("pdf", pdf);
  if ($("truth").files[0]) form.append("truth", $("truth").files[0]);

  const started = Date.now();
  const tick = () => setStatus(`O'qilyapti… ${Math.round((Date.now() - started) / 1000)} s (OCR)`);
  tick();
  const timer = setInterval(tick, 1000);
  $("run").disabled = true;
  try {
    const response = await fetch("/extract?rasmlar=true", { method: "POST", body: form });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `Server xatosi (${response.status})`);
    answer = body;
    render();
    setStatus(`Tayyor: ${body.vaqt.jami} s`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    clearInterval(timer);
    $("run").disabled = false;
  }
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

function render() {
  renderMeta();
  renderLegend();
  renderPages();
  renderFields();
  updateJson();
  $("result").hidden = false;
}

function renderMeta() {
  const t = answer.vaqt;
  const parts = [
    el("strong", {}, answer.fayl || "xat.pdf"),
    ` · ${t.sahifalar} sahifa · ${t.jami} s (OCR ${t.ocr} s, ${t.ocr_soni} marta)`,
  ];
  if (answer.solishtirish) {
    const rows = Object.values(answer.solishtirish);
    const ok = rows.filter((r) => r.mos === true).length;
    parts.push(` · to'g'ri javob bilan mos: ${ok} / ${rows.length}`);
  }
  $("meta").replaceChildren(...parts);
}

function renderLegend() {
  const items = FIELDS.filter((f) => answer.joylar?.[f.key]).map((f) =>
    el("span", { className: `f-${f.key}` }, f.short),
  );
  items.push(el("span", { className: "plain" }, "⚠ uzuq ramka — tekshirish kerak (ko'pincha qo'lyozma)"));
  $("legend").replaceChildren(...items);
}

// ── Chap: sahifalar va ramkalar ──
function renderPages() {
  const flags = new Set(answer.tekshirish_kerak || []);
  const pages = (answer.rasmlar || []).map((src, i) => {
    const page = el("div", { className: "page" }, el("img", { src, alt: `${i + 1}-sahifa` }));
    for (const field of FIELDS) {
      for (const b of answer.joylar?.[field.key] || []) {
        if (b.sahifa === i + 1) page.append(boxElement(field, b, flags.has(field.key)));
      }
    }
    page.append(el("span", { className: "page-no" }, `${i + 1}-sahifa`));
    return page;
  });
  $("pages").replaceChildren(...pages);
}

function boxElement(field, b, flagged) {
  const box = el(
    "div",
    { className: `box f-${field.key}${flagged ? " flag" : ""}`, title: field.label },
    el("span", { className: "tag" }, flagged ? `⚠ ${field.short}` : field.short),
  );
  Object.assign(box.style, {
    left: `${b.x0 * 100}%`,
    top: `${b.y0 * 100}%`,
    width: `${(b.x1 - b.x0) * 100}%`,
    height: `${(b.y1 - b.y0) * 100}%`,
  });
  box.dataset.field = field.key;
  box.addEventListener("mouseenter", () => highlight(field.key, true));
  box.addEventListener("mouseleave", () => highlight(field.key, false));
  box.addEventListener("click", () => {
    const input = $(`in-${field.key}`);
    input.scrollIntoView({ block: "center", behavior: "smooth" });
    input.focus({ preventScroll: true });
  });
  return box;
}

function highlight(key, on) {
  document.querySelectorAll(`[data-field="${key}"]`).forEach((n) => n.classList.toggle("active", on));
}

// ── O'ng: maydonlar ──
function renderFields() {
  const flags = new Set(answer.tekshirish_kerak || []);
  $("fields").replaceChildren(...FIELDS.map((f) => fieldCard(f, flags.has(f.key))));
}

function fieldCard(field, flagged) {
  const input = el("input", { id: `in-${field.key}`, value: valueOf(answer, field.key) ?? "" });
  input.addEventListener("input", updateJson);

  const head = el("div", { className: "card-head" }, el("label", { htmlFor: input.id }, field.label));
  if (flagged) head.append(el("span", { className: "badge" }, "⚠ Tekshiring"));
  const card = el("div", { className: `card f-${field.key}` }, head, input);
  card.dataset.field = field.key;

  const suggestions = suggestionsOf(answer, field.key);
  if (suggestions.length) {
    card.append(el("p", { className: "hint" }, "AI takliflari (bosilsa maydonga yoziladi):"));
    const chips = suggestions.map((value) => {
      const chip = el("button", { type: "button", className: "chip" }, value);
      chip.addEventListener("click", () => {
        input.value = value;
        updateJson();
      });
      return chip;
    });
    card.append(el("div", { className: "chips" }, ...chips));
  } else if (flagged && !input.value && answer.joylar?.[field.key]) {
    card.append(el("p", { className: "hint" }, "O'qilmadi — chapdagi ramka ichidan o'qib yozing."));
  }

  const truth = answer.solishtirish?.[field.key];
  if (truth) card.append(truthRow(truth));
  if (field.key === "hujjat_junatuvchi_tashkilot") card.append(confirmRow(input));

  card.addEventListener("mouseenter", () => highlight(field.key, true));
  card.addEventListener("mouseleave", () => highlight(field.key, false));
  input.addEventListener("focus", () => {
    const box = document.querySelector(`.box[data-field="${field.key}"]`);
    if (box) box.scrollIntoView({ block: "center", behavior: "smooth" });
  });
  return card;
}

function truthRow(row) {
  const [mark, cls] =
    row.mos === true ? ["✓", "ok"] : row.mos === false ? ["✗", "bad"] : ["–", "none"];
  const parts = [el("span", { className: cls }, mark), " To'g'ri javob: ", row.togri ?? "(bo'sh)"];
  if ("taklif_mos" in row) parts.push(row.taklif_mos ? " · taklif to'g'ri" : " · taklif xato");
  return el("div", { className: "truth" }, ...parts);
}

/** Jo'natuvchi: xodim nomni tasdiqlasa, keyingi xatlarda shu blank avtomatik taniladi. */
function confirmRow(input) {
  const note = el("span", { className: "hint" });
  const button = el("button", { type: "button", className: "secondary" }, "Tasdiqlash va eslab qolish");
  button.addEventListener("click", async () => {
    const nom = input.value.trim();
    if (!nom) {
      note.textContent = "Avval nomni yozing yoki taklifni tanlang.";
      return;
    }
    button.disabled = true;
    try {
      const response = await fetch("/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blank_id: answer.blank_id, nom }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Server xatosi (${response.status})`);
      note.textContent = "Saqlandi: bu tashkilotning keyingi xatlari avtomatik taniladi.";
    } catch (error) {
      note.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  return el("div", { className: "confirm" }, button, note);
}

// ── Yakuniy JSON: xodim tekshirgan (o'zgartirgan) qiymatlar, EDO shaklida ──
function updateJson() {
  const read = (key) => $(`in-${key}`)?.value.trim() || null;
  const rekvizit = Object.fromEntries(REKVIZIT.map((key) => [key, read(key)]));
  const boshqarma = read("boshqarma");
  const final = {
    rekvizit_document: rekvizit,
    tasks: [{ asosiy_ijrochilar_boshqarmalari: boshqarma ? [boshqarma] : [] }],
  };
  $("json").textContent = JSON.stringify(final, null, 2);
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText($("json").textContent);
    $("copy").textContent = "Nusxa olindi";
  } catch {
    $("copy").textContent = "Nusxa olinmadi";
  }
  setTimeout(() => ($("copy").textContent = "Nusxa olish"), 1500);
}

$("upload").addEventListener("submit", analyze);
$("copy").addEventListener("click", copyJson);
