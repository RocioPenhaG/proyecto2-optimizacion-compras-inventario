import type { Page, Route } from "@playwright/test";
import type {
  CorridaAnalytics,
  TendenciaLinealItem,
  TendenciaVisualResponse,
} from "../../../src/services/api";

export const MOCK_CORRIDA_CON_TENDENCIAS = 101;
export const MOCK_CORRIDA_SIN_TENDENCIAS = 102;

export const MOCK_TENDENCIA_ESTABLE = 201;
export const MOCK_TENDENCIA_DECRECIENTE = 202;
export const MOCK_TENDENCIA_CRECIENTE = 203;
export const MOCK_TENDENCIA_VISUAL_INSUF = 299;

const E2E_USER = {
  id: 1,
  username: "compras",
  email: "compras@test.local",
  first_name: "Compras",
  last_name: "E2E",
  role: "COMPRAS",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export function buildCorrida(overrides: Partial<CorridaAnalytics> & { id: number }): CorridaAnalytics {
  return {
    id: overrides.id,
    task_id: overrides.task_id ?? `task-${overrides.id}`,
    estado: overrides.estado ?? "SUCCESS",
    metodo: "MANUAL",
    fecha_ejecucion: overrides.fecha_ejecucion ?? "2026-05-10T12:00:00Z",
    fecha_desde: "2026-04-01",
    fecha_hasta: "2026-04-30",
    queued_at: null,
    started_at: "2026-05-10T11:59:00Z",
    finished_at: "2026-05-10T12:00:00Z",
    registros_procesados: overrides.registros_procesados ?? 120,
    puntos_usados: overrides.puntos_usados ?? 90,
    mensaje: "OK",
    error_detalle: "",
    resultados_tendencia_count: overrides.resultados_tendencia_count ?? 0,
    productos_candidatos_tendencia: overrides.productos_candidatos_tendencia ?? 3,
  };
}

export function buildTendencia(
  overrides: Partial<TendenciaLinealItem> & { id: number; pendiente: number },
): TendenciaLinealItem {
  return {
    id: overrides.id,
    producto_id: overrides.producto_id ?? overrides.id,
    producto_nombre: overrides.producto_nombre ?? `Producto ${overrides.id}`,
    producto_sku: overrides.producto_sku ?? `SKU-${overrides.id}`,
    periodicidad: "DAILY",
    puntos_usados: overrides.puntos_usados ?? 5,
    pendiente: overrides.pendiente,
    prediccion_siguiente: overrides.prediccion_siguiente ?? 20,
    stock_actual: overrides.stock_actual ?? 15,
    stock_minimo: overrides.stock_minimo ?? 10,
    cantidad_sugerida_reposicion: overrides.cantidad_sugerida_reposicion ?? 0,
    criterio_reposicion: overrides.criterio_reposicion ?? "Stock suficiente",
    fecha_inicio: overrides.fecha_inicio ?? "2026-04-01",
    fecha_fin: overrides.fecha_fin ?? "2026-04-05",
  };
}

export function buildVisualOk(tendenciaId: number): TendenciaVisualResponse {
  return {
    id: tendenciaId,
    corrida_id: MOCK_CORRIDA_CON_TENDENCIAS,
    producto_id: tendenciaId,
    producto: "Producto Alfa",
    sku: "SKU-ALFA",
    periodicidad: "DAILY",
    historico: [
      { fecha: "2026-04-01", consumo: 10 },
      { fecha: "2026-04-02", consumo: 12 },
      { fecha: "2026-04-03", consumo: 14 },
    ],
    tendencia: [
      { fecha: "2026-04-01", valor: 10 },
      { fecha: "2026-04-02", valor: 11 },
      { fecha: "2026-04-03", valor: 12 },
    ],
    prediccion: { fecha: "2026-04-04", valor: 13 },
  };
}

export function buildVisualInsufficient(tendenciaId: number): TendenciaVisualResponse {
  return {
    id: tendenciaId,
    corrida_id: MOCK_CORRIDA_CON_TENDENCIAS,
    producto_id: tendenciaId,
    producto: "Producto Insuficiente",
    sku: "SKU-INS",
    periodicidad: "DAILY",
    historico: [{ fecha: "2026-04-01", consumo: 8 }],
    tendencia: [],
    prediccion: { fecha: "2026-04-02", valor: 0 },
    detail: "No hay datos suficientes para visualizar la tendencia.",
  };
}

export interface AnalyticsVisualMockConfig {
  corridas?: CorridaAnalytics[];
  tendenciasByCorrida?: Record<number, TendenciaLinealItem[]>;
  visualByTendenciaId?: Record<number, TendenciaVisualResponse>;
}

export const DEFAULT_VISUAL_MOCKS: AnalyticsVisualMockConfig = {
  corridas: [
    buildCorrida({
      id: MOCK_CORRIDA_CON_TENDENCIAS,
      resultados_tendencia_count: 3,
      productos_candidatos_tendencia: 3,
    }),
    buildCorrida({
      id: MOCK_CORRIDA_SIN_TENDENCIAS,
      resultados_tendencia_count: 0,
      productos_candidatos_tendencia: 2,
      fecha_ejecucion: "2026-05-08T10:00:00Z",
    }),
  ],
  tendenciasByCorrida: {
    [MOCK_CORRIDA_CON_TENDENCIAS]: [
      buildTendencia({ id: MOCK_TENDENCIA_ESTABLE, pendiente: 0, producto_nombre: "Prod Estable" }),
      buildTendencia({ id: MOCK_TENDENCIA_DECRECIENTE, pendiente: -3, producto_nombre: "Prod Decreciente" }),
      buildTendencia({ id: MOCK_TENDENCIA_CRECIENTE, pendiente: 2, producto_nombre: "Prod Creciente" }),
    ],
    [MOCK_CORRIDA_SIN_TENDENCIAS]: [],
  },
  visualByTendenciaId: {
    [MOCK_TENDENCIA_ESTABLE]: buildVisualOk(MOCK_TENDENCIA_ESTABLE),
    [MOCK_TENDENCIA_DECRECIENTE]: buildVisualOk(MOCK_TENDENCIA_DECRECIENTE),
    [MOCK_TENDENCIA_CRECIENTE]: buildVisualOk(MOCK_TENDENCIA_CRECIENTE),
    [MOCK_TENDENCIA_VISUAL_INSUF]: buildVisualInsufficient(MOCK_TENDENCIA_VISUAL_INSUF),
  },
};

/** Registra mocks de API para dashboard + analytics (sin depender de datos reales). */
export async function installAnalyticsVisualMocks(
  page: Page,
  config: AnalyticsVisualMockConfig = DEFAULT_VISUAL_MOCKS,
) {
  const corridas = config.corridas ?? DEFAULT_VISUAL_MOCKS.corridas ?? [];
  const tendenciasByCorrida = config.tendenciasByCorrida ?? DEFAULT_VISUAL_MOCKS.tendenciasByCorrida ?? {};
  const visualByTendenciaId = config.visualByTendenciaId ?? DEFAULT_VISUAL_MOCKS.visualByTendenciaId ?? {};

  await page.route("**/api/auth/login/", async (route) => {
    if (route.request().method() === "POST") {
      return json(route, { access: "e2e-access-token", refresh: "e2e-refresh-token" });
    }
    return route.continue();
  });

  await page.route("**/api/auth/me/", async (route) => json(route, E2E_USER));
  await page.route("**/api/auth/refresh/", async (route) =>
    json(route, { access: "e2e-access-token" }),
  );

  await page.route("**/api/dashboard/**", async (route) =>
    json(route, {
      solicitudes_por_estado: { SOLICITADO: 1, EN_REVISION: 0 },
      tiempo_promedio_aprobacion_dias: 2,
      productos_stock_critico: 0,
      stock_critico: {
        resumen: { total_productos_criticos: 0, total_sin_stock: 0, total_cobertura_baja: 0 },
        resultados: [],
      },
      filtro_desde: "2026-04-01",
      filtro_hasta: "2026-04-30",
    }),
  );

  await page.route("**/api/analytics/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path.includes("/etl/corridas/") && path.endsWith("/tendencias/")) {
      const match = path.match(/\/corridas\/(\d+)\/tendencias\/?$/);
      const corridaId = match ? Number(match[1]) : 0;
      const results = tendenciasByCorrida[corridaId] ?? [];
      return json(route, {
        corrida_id: corridaId,
        task_id: `task-${corridaId}`,
        count: results.length,
        results,
      });
    }

    if (path.includes("/etl/tendencias/") && path.endsWith("/visual/")) {
      const match = path.match(/\/tendencias\/(\d+)\/visual\/?$/);
      const tendenciaId = match ? Number(match[1]) : 0;
      const visual = visualByTendenciaId[tendenciaId];
      if (!visual) {
        return json(route, { detail: "No existe la tendencia solicitada." }, 404);
      }
      return json(route, visual);
    }

    if (/\/analytics\/etl\/corridas\/?$/.test(path)) {
      return json(route, { count: corridas.length, results: corridas });
    }

    if (path.includes("/resumen-consumo")) {
      return json(route, {
        total_salidas: 100,
        productos_distintos: 3,
        dias_con_consumo: 10,
        promedio_diario_periodo: 10,
        filas_hecho_consumo: 30,
        meses_con_resumen_mensual: 1,
        filtro_desde: url.searchParams.get("desde") ?? "2026-04-01",
        filtro_hasta: url.searchParams.get("hasta") ?? "2026-04-30",
      });
    }

    if (path.includes("/top-productos-consumidos")) {
      return json(route, {
        top_productos: [
          { producto_id: 1, producto_sku: "SKU-1", producto_nombre: "Prod 1", cantidad_total: 50 },
        ],
        filtro_desde: "2026-04-01",
        filtro_hasta: "2026-04-30",
        limit: 10,
      });
    }

    if (path.includes("/ultima-corrida")) {
      return json(route, { corrida: corridas[0] ?? null });
    }

    if (path.includes("/demanda-vs-consumo")) {
      return json(route, {
        periodo: { desde: "2026-04-01", hasta: "2026-04-30", dias: 30 },
        desde: "2026-04-01",
        hasta: "2026-04-30",
        limit: 50,
        resumen: {
          total_solicitado: 0,
          total_consumido: 0,
          mayor_solicitud_que_consumo: 0,
          mayor_consumo_que_solicitud: 0,
          coherentes: 0,
          riesgo_alto: 0,
          baja_cobertura: 0,
        },
        resultados: [],
      });
    }

    if (path.includes("/habitos-resumen")) {
      return json(route, {
        periodo: { desde: "2026-04-01", hasta: "2026-04-30", dias: 30 },
        resumen_mensual: [],
        consumo_por_dia_semana: [],
      });
    }

    return json(route, {});
  });
}

export async function gotoDashboardWithMocks(
  page: Page,
  config?: AnalyticsVisualMockConfig,
) {
  await installAnalyticsVisualMocks(page, config);
  await page.goto("/login");
  await page.getByTestId("login-username").fill("compras");
  await page.getByTestId("login-password").fill("segupak123");
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/(dashboard)?$/);
  await page.goto("/dashboard");
  await page.getByTestId("dashboard-page").waitFor({ state: "visible" });
  await page.getByTestId("corridas-etl-section").scrollIntoViewIfNeeded();
}
