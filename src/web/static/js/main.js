// Sahifa: ikki tab — "Bitta xat" va "Papka (katalog)".

import { initBatch } from "./batch.js";
import { $ } from "./dom.js";
import { initSingle } from "./single.js";

function openTab(name) {
  for (const tab of ["single", "batch"]) {
    $(tab).hidden = tab !== name;
    $(`tab-${tab}`).setAttribute("aria-selected", String(tab === name));
  }
}

$("tab-single").addEventListener("click", () => openTab("single"));
$("tab-batch").addEventListener("click", () => openTab("batch"));
initSingle();
initBatch(() => openTab("single"));
