// Maydonlar: javobdagi kalit, sahifadagi nomi va qiymatni javobdan o'qish.

export const FIELDS = [
  { key: "hujjat_junatuvchi_tashkilot", label: "Jo'natuvchi tashkilot", short: "Jo'natuvchi" },
  { key: "hujjat_sana", label: "Hujjat sanasi", short: "Sana" },
  { key: "hujjat_raqami", label: "Hujjat raqami", short: "Raqam" },
  { key: "imzolagan_shaxs", label: "Imzolagan shaxs", short: "Imzo" },
  { key: "hujjatning_qisqacha_mazmuni", label: "Qisqacha mazmun", short: "Mazmun" },
  { key: "boshqarma", label: "Boshqarma (task)", short: "Boshqarma" },
];
export const REKVIZIT = FIELDS.map((f) => f.key).filter((k) => k !== "boshqarma");

export function valueOf(answer, key) {
  if (key === "boshqarma") {
    return answer.tasks?.[0]?.asosiy_ijrochilar_boshqarmalari?.[0] ?? null;
  }
  return answer.rekvizit_document?.[key] ?? null;
}

export function suggestionsOf(answer, key) {
  const value = answer.takliflar?.[key];
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

export function isFlagged(answer, key) {
  return (answer.tekshirish_kerak || []).includes(key);
}
