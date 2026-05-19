import { apiErrorMessage } from "@/utils/apiFetch";
import { buildAnalyticsQueryParams, resolveAnalyticsQueryRange } from "@/utils/analyticsDateRange";

const API_BASE = "/api";

export interface LoginResponse {
  access: string;
  refresh: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch (err) {
    throw new Error(
      "No se pudo conectar al servidor. ¿Está el backend en marcha en http://localhost:8000?"
    );
  }
  if (!res.ok) {
    const contentType = res.headers.get("content-type");
    let message = `Error al iniciar sesión (${res.status})`;
    if (contentType?.includes("application/json")) {
      const data = await res.json().catch(() => ({}));
      const detail = data.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.join(" ");
      else if (detail && typeof detail === "object") message = JSON.stringify(detail);
      else if (data.non_field_errors?.length) message = data.non_field_errors.join(" ");
      else if (data.username?.length) message = data.username.join(" ");
      else if (data.password?.length) message = data.password.join(" ");
    } else {
      const text = await res.text();
      if (text.length > 0) {
        const snippet = text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
        if (snippet) message += ": " + snippet;
      }
    }
    throw new Error(message);
  }
  return res.json();
}

export async function refreshToken(
  refresh: string,
  init?: RequestInit,
): Promise<{ access: string }> {
  const res = await fetch(`${API_BASE}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
    ...init,
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "Sesión expirada"));
  return res.json();
}

export async function getMe(accessToken: string, init?: RequestInit): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    ...init,
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "No autorizado"));
  return res.json();
}

export interface CorridaAnalytics {
  id: number;
  task_id: string | null;
  estado: string;
  metodo?: string;
  fecha_ejecucion: string;
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  registros_procesados: number;
  puntos_usados: number;
  mensaje: string;
  error_detalle: string;
  resultados_tendencia_count: number;
  /** Productos con OUT en la ventana de tendencia (null si aún no aplica o no se puede inferir). */
  productos_candidatos_tendencia: number | null;
}

export interface ResumenConsumoResponse {
  total_salidas: number;
  productos_distintos: number;
  dias_con_consumo: number;
  promedio_diario_periodo: number;
  filas_hecho_consumo: number;
  meses_con_resumen_mensual: number;
  filtro_desde: string;
  filtro_hasta: string;
}

export interface TopProductoConsumido {
  producto_id: number;
  producto_sku: string;
  producto_nombre: string;
  cantidad_total: number;
}

export interface TopProductosConsumidosResponse {
  top_productos: TopProductoConsumido[];
  filtro_desde: string;
  filtro_hasta: string;
  limit: number;
}

export type DemandaVsConsumoEstado = "solicitado_mayor" | "consumo_mayor" | "coherente";

export interface DemandaVsConsumoItem {
  producto_id: number;
  sku: string;
  nombre: string;
  cantidad_solicitada: number;
  cantidad_consumida: number;
  diferencia: number;
  estado: DemandaVsConsumoEstado;
  lectura: string;
  demanda_vs_consumo: string;
  habito_detectado: string;
  stock_actual: number;
  consumo_promedio_diario: number;
  cobertura_dias: number | null;
  cobertura_texto: string;
  cobertura_fuente?: "historico" | "proyeccion";
  riesgo: "Alto" | "Medio" | "Bajo";
  recomendacion: string;
  alerta_proyeccion?: boolean;
  consumo_proyectado_semana?: number;
  consumo_proyectado_mes?: number;
  consumo_proyectado_trimestre?: number;
  cantidad_sugerida_reposicion?: number;
}

export interface DemandaVsConsumoResumen {
  total_solicitado: number;
  total_consumido: number;
  mayor_solicitud_que_consumo: number;
  mayor_consumo_que_solicitud: number;
  coherentes: number;
  riesgo_alto: number;
  consumo_mayor_solicitud: number;
  demanda_coherente: number;
  baja_cobertura: number;
  mayor_solicitud_consumo: number;
}

export interface DemandaVsConsumoResponse {
  desde: string;
  hasta: string;
  limit: number;
  resumen: DemandaVsConsumoResumen;
  resultados: DemandaVsConsumoItem[];
}

export interface UltimaCorridaResponse {
  corrida: CorridaAnalytics | null;
}

export interface CorridasResponse {
  count: number;
  results: CorridaAnalytics[];
}

export interface EstadoCorridaResponse {
  task_id: string | null;
  estado: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  registros_procesados: number;
  puntos_usados: number;
  mensaje: string;
  error_detalle: string;
  resultados_tendencia_count: number;
  productos_candidatos_tendencia: number | null;
}

export interface TendenciaLinealItem {
  id: number;
  producto_id: number;
  producto_nombre: string;
  producto_sku: string;
  periodicidad: string;
  puntos_usados: number;
  pendiente: number;
  prediccion_siguiente: number;
  stock_actual: number;
  stock_minimo: number;
  cantidad_sugerida_reposicion: number;
  criterio_reposicion: string;
  fecha_inicio: string;
  fecha_fin: string;
}

export interface TendenciasCorridaResponse {
  corrida_id: number;
  task_id: string | null;
  count: number;
  results: TendenciaLinealItem[];
}

export interface TendenciaVisualPuntoHistorico {
  fecha: string;
  consumo: number;
}

export interface TendenciaVisualPuntoLinea {
  fecha: string;
  valor: number;
}

export interface TendenciaVisualPrediccion {
  fecha: string;
  valor: number;
}

export interface TendenciaVisualResponse {
  id: number;
  corrida_id: number;
  producto_id: number;
  producto: string;
  sku: string;
  periodicidad: string;
  historico: TendenciaVisualPuntoHistorico[];
  tendencia: TendenciaVisualPuntoLinea[];
  prediccion: TendenciaVisualPrediccion;
  detail?: string;
}

export async function getAnalyticsResumenConsumo(
  accessToken: string,
  desde?: string,
  hasta?: string,
): Promise<ResumenConsumoResponse> {
  const range = resolveAnalyticsQueryRange(desde, hasta);
  const q = buildAnalyticsQueryParams(range.desde, range.hasta).toString();
  const res = await fetch(`${API_BASE}/analytics/resumen-consumo/?${q}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar resumen de consumo"));
  return res.json();
}

export async function getAnalyticsTopProductosConsumidos(
  accessToken: string,
  options?: { desde?: string; hasta?: string; limit?: number },
): Promise<TopProductosConsumidosResponse> {
  const range = resolveAnalyticsQueryRange(options?.desde, options?.hasta);
  const params = buildAnalyticsQueryParams(range.desde, range.hasta);
  if (options?.limit != null) params.set("limit", String(Math.min(50, Math.max(1, options.limit))));
  const q = params.toString();
  const res = await fetch(`${API_BASE}/analytics/top-productos-consumidos/?${q}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar top productos consumidos"));
  return res.json();
}

export async function getAnalyticsDemandaVsConsumo(
  accessToken: string,
  options?: { desde?: string; hasta?: string; limit?: number },
): Promise<DemandaVsConsumoResponse> {
  const range = resolveAnalyticsQueryRange(options?.desde, options?.hasta);
  const params = buildAnalyticsQueryParams(range.desde, range.hasta);
  if (options?.limit != null) params.set("limit", String(Math.min(100, Math.max(1, options.limit))));
  const q = params.toString();
  const res = await fetch(`${API_BASE}/analytics/demanda-vs-consumo/?${q}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar demanda vs consumo"));
  return res.json();
}

export async function getAnalyticsUltimaCorrida(accessToken: string): Promise<UltimaCorridaResponse> {
  const res = await fetch(`${API_BASE}/analytics/ultima-corrida/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar última corrida"));
  return res.json();
}

export async function getAnalyticsCorridas(accessToken: string, limit = 10): Promise<CorridasResponse> {
  const safeLimit = Math.max(1, Math.min(limit, 20));
  const res = await fetch(`${API_BASE}/analytics/etl/corridas/?limit=${safeLimit}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Error al cargar corridas ETL (${res.status})`);
  return res.json();
}

export async function getAnalyticsCorridaStatus(
  accessToken: string,
  taskId: string,
): Promise<EstadoCorridaResponse> {
  const res = await fetch(`${API_BASE}/analytics/etl/status/${encodeURIComponent(taskId)}/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Error al consultar estado ETL (${res.status})`);
  return res.json();
}

export async function getAnalyticsCorridaTendencias(
  accessToken: string,
  corridaId: number,
): Promise<TendenciasCorridaResponse> {
  const res = await fetch(`${API_BASE}/analytics/etl/corridas/${corridaId}/tendencias/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Error al consultar tendencias (${res.status})`);
  return res.json();
}

export async function getAnalyticsTendenciaVisual(
  accessToken: string,
  tendenciaId: number,
): Promise<TendenciaVisualResponse> {
  const res = await fetch(`${API_BASE}/analytics/etl/tendencias/${tendenciaId}/visual/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`Error al consultar detalle visual (${res.status})`);
  return res.json();
}
