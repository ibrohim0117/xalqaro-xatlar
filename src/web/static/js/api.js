// Serverga so'rovlar. Xato bo'lsa — o'zbekcha izoh bilan Error (server "detail" maydonidan).

async function readJson(response) {
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`Server javobi o'qilmadi (${response.status})`);
  }
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    throw new Error(detail || `Server xatosi (${response.status})`);
  }
  return body;
}

/** PDF (+ ixtiyoriy to'g'ri javob json'i) -> AI javobi. images: sahifalar rasmi ham kerakmi. */
export async function extract(pdf, truth = null, { images = false } = {}) {
  const form = new FormData();
  form.append("pdf", pdf);
  if (truth) form.append("truth", truth);
  const url = images ? "/extract?rasmlar=true" : "/extract";
  return readJson(await fetch(url, { method: "POST", body: form }));
}

/** Xodim tasdiqlagan jo'natuvchi nomi — xotiraga (keyingi xatlarda avtomatik taniladi). */
export async function confirmSender(blankId, nom) {
  const response = await fetch("/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ blank_id: blankId, nom }),
  });
  return readJson(response);
}
