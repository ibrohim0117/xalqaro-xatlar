// Papka rejimi: papkadagi barcha xatlar ketma-ket tahlil qilinadi, jadval va umumiy foizlar.
// Rahbar talabi (23.10): "bitta xatni yoki katalogdagi barcha xatlarni test qilish".
// Xatlar serverga birma-bir yuboriladi (OCR protsessorni band qiladi — parallel yuborilmaydi).

import { extract } from "./api.js";
import { $, el } from "./dom.js";
import { FIELDS, isFlagged, valueOf } from "./fields.js";
import { showAnswer, showLetter } from "./single.js";

let letters = []; // {name, pdf, truth}
let rows = []; // {letter, answer} yoki {letter, error}
let stopRequested = false;
let openSingle = () => {}; // "Ko'rish" bosilganda — "Bitta xat" tabiga o'tish

export function initBatch(openSingleTab) {
  $("folder").addEventListener("change", () =>
    loadEntries([...$("folder").files].map((file) => ({ path: file.webkitRelativePath || file.name, file }))),
  );
  $("batch-run").addEventListener("click", run);
  $("batch-stop").addEventListener("click", () => {
    stopRequested = true;
    setStatus("To'xtatilmoqda: joriy xat tugashini kutyapmiz…");
  });
  $("batch-csv").addEventListener("click", downloadCsv);
  openSingle = openSingleTab;
}

/**
 * Fayllarni xatlarga guruhlaydi. Har papka — bitta xat (DOC_xxx/{pdf, json}, bizga berilgan
 * xatlar shunday). Bitta papkada bir nechta PDF bo'lsa — har PDF alohida xat, json esa PDF bilan
 * bir xil nomli bo'lsagina olinadi.
 */
export function groupLetters(entries) {
  const byDir = new Map();
  for (const { path, file } of entries) {
    const slash = path.lastIndexOf("/");
    const dir = slash >= 0 ? path.slice(0, slash) : "";
    const name = path.slice(slash + 1);
    const group = byDir.get(dir) || { pdfs: [], jsons: [] };
    if (/\.pdf$/i.test(name)) group.pdfs.push({ name, file });
    else if (/\.json$/i.test(name)) group.jsons.push({ name, file });
    byDir.set(dir, group);
  }
  const stem = (name) => name.replace(/\.[^.]+$/, "");
  const found = [];
  for (const [dir, { pdfs, jsons }] of byDir) {
    if (pdfs.length === 1) {
      const truth = jsons.find((j) => stem(j.name) === stem(pdfs[0].name)) || (jsons.length === 1 ? jsons[0] : null);
      found.push({ name: dir.split("/").pop() || stem(pdfs[0].name), pdf: pdfs[0].file, truth: truth?.file || null });
    } else {
      for (const pdf of pdfs) {
        const truth = jsons.find((j) => stem(j.name) === stem(pdf.name));
        found.push({ name: stem(pdf.name), pdf: pdf.file, truth: truth?.file || null });
      }
    }
  }
  return found.sort((a, b) => a.name.localeCompare(b.name));
}

/** Tanlangan fayllar (yoki sinov uchun berilgan ro'yxat) -> xatlar. */
export function loadEntries(entries) {
  letters = groupLetters(entries);
  const withTruth = letters.filter((l) => l.truth).length;
  setStatus(
    letters.length
      ? `${letters.length} ta xat topildi, ${withTruth} tasida to'g'ri javob (json) bor.`
      : "Papkada PDF topilmadi.",
  );
  $("batch-run").disabled = !letters.length;
}

function setStatus(text) {
  $("batch-status").textContent = text;
}

// ── Ketma-ket tahlil ──
async function run() {
  rows = [];
  stopRequested = false;
  $("batch-run").disabled = true;
  $("batch-stop").disabled = false;
  $("batch-csv").disabled = true;
  $("batch-result").hidden = false;
  $("batch-rows").replaceChildren();
  renderSummary();
  for (const [i, letter] of letters.entries()) {
    if (stopRequested) break;
    setStatus(`${i + 1} / ${letters.length}: ${letter.name} o'qilyapti…`);
    $("batch-progress").value = i / letters.length;
    let row;
    try {
      row = { letter, answer: await extract(letter.pdf, letter.truth) };
    } catch (error) {
      row = { letter, error: error.message };
    }
    rows.push(row);
    $("batch-rows").append(tableRow(row, rows.length));
    renderSummary();
  }
  $("batch-progress").value = rows.length / letters.length;
  const failed = rows.filter((r) => r.error).length;
  setStatus(
    `${stopRequested ? "To'xtatildi" : "Tayyor"}: ${rows.length} / ${letters.length} xat` +
      (failed ? `, ${failed} tasi o'qilmadi` : ""),
  );
  $("batch-run").disabled = false;
  $("batch-stop").disabled = true;
  $("batch-csv").disabled = !rows.length;
}

// ── Jadval ──
/** Maydon belgisi: json bo'lsa — ✓/✗/– (AI yozmagan), bo'lmasa — • (yozdi) yoki ⚠ (tekshirish kerak). */
function mark(answer, key) {
  const compared = answer.solishtirish?.[key];
  if (compared) {
    const [text, cls] =
      compared.mos === true ? ["✓", "ok"] : compared.mos === false ? ["✗", "bad"] : ["–", "none"];
    const hint = "taklif_mos" in compared ? (compared.taklif_mos ? " t✓" : " t✗") : "";
    return el("td", { className: `mark ${cls}`, title: "t✓ — taklif to'g'ri" }, text + hint);
  }
  if (isFlagged(answer, key)) return el("td", { className: "mark warn" }, "⚠");
  return el("td", { className: "mark none" }, valueOf(answer, key) ? "•" : "–");
}

function tableRow({ letter, answer, error }, number) {
  const open = el("button", { type: "button", className: "secondary small" }, "Ko'rish");
  open.addEventListener("click", () => {
    openSingle();
    // tahlil qilingan bo'lsa — tayyor natija (bir zumda); xato bilan tugagan bo'lsa — qayta tahlil
    if (answer) showAnswer(answer, letter.pdf, letter.truth);
    else showLetter(letter.pdf, letter.truth);
  });
  const cells = [el("td", {}, number), el("td", { className: "name" }, letter.name)];
  if (error) {
    cells.push(el("td", { className: "error", colSpan: FIELDS.length + 3 }, error));
  } else {
    const t = answer.vaqt;
    cells.push(el("td", { className: "num" }, t.jami.toFixed(1)), el("td", { className: "num" }, t.ocr.toFixed(1)));
    for (const field of FIELDS) cells.push(mark(answer, field.key));
    cells.push(el("td", { className: "num" }, (answer.tekshirish_kerak || []).length));
  }
  cells.push(el("td", {}, open));
  return el("tr", {}, ...cells);
}

// ── Umumiy hisob ──
/**
 * Har maydon: aniqlik = to'g'ri / hamma xat; qamrov = javob berilgan / hamma xat;
 * ishonchlilik = to'g'ri / javob berilgan; taklif — maydon bo'sh, taklif to'g'ri chiqqanlari.
 * Qoida src/evaluation/evaluate.py dagi FieldScore bilan bir xil. Faqat json bor xatlar sanaladi.
 */
export function summarize(answers) {
  const compared = answers.filter((a) => a.solishtirish);
  return FIELDS.map((field) => {
    const marks = compared.map((a) => a.solishtirish[field.key]);
    const correct = marks.filter((m) => m.mos === true).length;
    const answered = marks.filter((m) => m.mos !== null).length;
    const suggested = marks.filter((m) => "taklif_mos" in m);
    return {
      field,
      total: marks.length,
      correct,
      answered,
      suggestionsRight: suggested.filter((m) => m.taklif_mos).length,
      suggestions: suggested.length,
    };
  });
}

const pct = (part, whole) => (whole ? `${Math.round((100 * part) / whole)}%` : "—");

function renderSummary() {
  const answers = rows.filter((r) => r.answer).map((r) => r.answer);
  const times = answers.map((a) => a.vaqt.jami).sort((a, b) => a - b);
  const total = times.reduce((s, t) => s + t, 0);
  const ocr = answers.reduce((s, a) => s + a.vaqt.ocr, 0);
  const median = times.length ? times[Math.floor((times.length - 1) / 2)] : 0;
  $("batch-time").textContent = times.length
    ? `Vaqt: o'rtacha (median) ${median.toFixed(1)} s, eng sekin ${times.at(-1).toFixed(1)} s, ` +
      `jami ${total.toFixed(0)} s; shundan OCR ${pct(ocr, total)}`
    : "";

  const stats = summarize(answers);
  const hasTruth = stats[0].total > 0;
  $("batch-summary").hidden = !hasTruth;
  if (!hasTruth) return;
  $("batch-summary-rows").replaceChildren(
    ...stats.map((s) =>
      el(
        "tr",
        {},
        el("td", { className: `f-${s.field.key} field-name` }, s.field.label),
        el("td", { className: "num" }, `${pct(s.correct, s.total)} (${s.correct}/${s.total})`),
        el("td", { className: "num" }, pct(s.answered, s.total)),
        el("td", { className: "num" }, pct(s.correct, s.answered)),
        el("td", { className: "num" }, s.suggestions ? `${s.suggestionsRight}/${s.suggestions}` : "—"),
      ),
    ),
  );
}

// ── CSV: har xat va har maydon — AI qiymati, to'g'ri javob, mos (fayl faqat shu kompyuterga yoziladi) ──
function downloadCsv() {
  const header = ["xat", "vaqt_jami", "vaqt_ocr", "sahifalar", "xato"];
  for (const f of FIELDS) header.push(`${f.key}_ai`, `${f.key}_togri`, `${f.key}_mos`);
  const lines = [header];
  for (const { letter, answer, error } of rows) {
    if (error) {
      lines.push([letter.name, "", "", "", error]);
      continue;
    }
    const line = [letter.name, answer.vaqt.jami, answer.vaqt.ocr, answer.vaqt.sahifalar, ""];
    for (const f of FIELDS) {
      const c = answer.solishtirish?.[f.key];
      const mos = !c ? "" : c.mos === null ? "none" : String(c.mos); // none — AI yozmagan
      line.push(valueOf(answer, f.key) ?? "", c?.togri ?? "", mos);
    }
    lines.push(line);
  }
  const quote = (v) => `"${String(v).replaceAll('"', '""')}"`;
  const csv = "﻿" + lines.map((l) => l.map(quote).join(",")).join("\r\n"); // ﻿ — Excel UTF-8
  const link = el("a", {
    href: URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })),
    download: "natijalar.csv",
  });
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
