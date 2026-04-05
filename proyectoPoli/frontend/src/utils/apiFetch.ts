/**
 * Mensaje de error legible desde respuestas JSON del API (DRF / middleware).
 */
export async function apiErrorMessage(res: Response, fallback: string): Promise<string> {
  if (res.status === 401) return "Sesión expirada o no válida. Vuelva a iniciar sesión.";
  const ct = res.headers.get("content-type");
  if (ct?.includes("application/json")) {
    const data = (await res.json().catch(() => null)) as Record<string, unknown> | null;
    if (data?.detail != null) {
      const d = data.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) return d.map(String).join(" ");
    }
  }
  return `${fallback} (${res.status})`;
}
