/** Formato de cantidades en unidades (consumo, stock, proyecciones): siempre entero redondeado. */

export function roundUnidades(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return Math.round(n);
}

export function fmtUnidades(value: unknown, emptyLabel = "—"): string {
  const n = roundUnidades(value);
  if (n == null) return emptyLabel;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
