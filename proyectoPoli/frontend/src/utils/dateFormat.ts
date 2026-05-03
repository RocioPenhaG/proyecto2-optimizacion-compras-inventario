/**
 * Formato de fecha visible DD-MM-YYYY (evita parsear con Date para no desplazar el día por TZ).
 */
export function formatIsoDateToDMY(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const slice = value.trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(slice)) return value;
  const [y, m, d] = slice.split("-");
  return `${d}-${m}-${y}`;
}

/** Fecha-hora ISO → DD-MM-YYYY HH:mm (hora local del navegador). */
export function formatIsoDateTimeToDMYHM(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
