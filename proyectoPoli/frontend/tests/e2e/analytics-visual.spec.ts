/**
 * E2E visuales del módulo analítico (TC02.3, TC03.3, TC06.x, TC07.2).
 * Usa mocks de API (`page.route`); no requiere datos reales en BD.
 *
 * Ejecución:
 *   npx playwright test tests/e2e/analytics-visual.spec.ts
 * Con servidor ya levantado:
 *   $env:E2E_SKIP_WEBSERVER="1"; $env:E2E_BASE_URL="http://localhost:5173"
 */
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });
import {
  buildCorrida,
  buildTendencia,
  buildVisualInsufficient,
  buildVisualOk,
  gotoDashboardWithMocks,
  installAnalyticsVisualMocks,
  MOCK_CORRIDA_CON_TENDENCIAS,
  MOCK_CORRIDA_SIN_TENDENCIAS,
  MOCK_TENDENCIA_CRECIENTE,
  MOCK_TENDENCIA_DECRECIENTE,
  MOCK_TENDENCIA_ESTABLE,
  MOCK_TENDENCIA_VISUAL_INSUF,
  type AnalyticsVisualMockConfig,
} from "./helpers/analytics-mocks";

async function expectNoBrokenUiText(page: import("@playwright/test").Page) {
  const section = page.getByTestId("corridas-etl-section");
  await expect(section).not.toContainText("undefined");
  await expect(section).not.toContainText("NaN");
}

test.describe("TC02.3 — Interpretación visual de pendiente negativa o nula", () => {
  test.beforeEach(async ({ page }) => {
    await gotoDashboardWithMocks(page);
  });

  test("TC02.3 — variación diaria e interpretación según pendiente", async ({ page }) => {
    await expect(page.getByTestId("tendencias-table")).toBeVisible();

    await expect(page.getByTestId(`tendencia-variacion-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText("+0");
    await expect(page.getByTestId(`tendencia-interpretacion-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText(
      "Estable",
    );

    await expect(page.getByTestId(`tendencia-variacion-${MOCK_TENDENCIA_DECRECIENTE}`)).toHaveText(
      "-3",
    );
    await expect(
      page.getByTestId(`tendencia-interpretacion-${MOCK_TENDENCIA_DECRECIENTE}`),
    ).toHaveText("Decreciente");

    await expect(page.getByTestId(`tendencia-variacion-${MOCK_TENDENCIA_CRECIENTE}`)).toHaveText(
      "+2",
    );
    await expect(
      page.getByTestId(`tendencia-interpretacion-${MOCK_TENDENCIA_CRECIENTE}`),
    ).toHaveText("Creciente");

    await expectNoBrokenUiText(page);
  });
});

test.describe("TC03.3 — Visibilidad y trazabilidad visual de tendencias", () => {
  test("TC03.3 — historial de corridas y detalle al seleccionar corrida", async ({ page }) => {
    await gotoDashboardWithMocks(page);

    await expect(page.getByTestId("corridas-etl-section")).toBeVisible();
    await expect(page.getByTestId("corridas-table")).toBeVisible();

    const celdaTendencias = page.getByTestId(
      `corrida-tendencias-count-${MOCK_CORRIDA_CON_TENDENCIAS}`,
    );
    await expect(celdaTendencias).toBeVisible();
    await expect(celdaTendencias).toContainText(/productos analizados|productos con tendencia/i);

    const filaConTendencias = page.getByTestId(`corrida-row-${MOCK_CORRIDA_CON_TENDENCIAS}`);
    await expect(filaConTendencias).toHaveClass(/bg-blue-50/);

    await page.getByTestId(`corrida-row-${MOCK_CORRIDA_SIN_TENDENCIAS}`).click();
    await expect(page.getByTestId("tendencias-sin-resultados")).toBeVisible();
    await expect(page.getByTestId(`corrida-tendencias-count-${MOCK_CORRIDA_SIN_TENDENCIAS}`)).toContainText(
      /0 de \d+ productos analizados|sin tendencias/i,
    );

    await filaConTendencias.click();
    await expect(page.getByTestId("tendencias-panel")).toBeVisible();
    await expect(page.getByText("Detalle de tendencias lineales")).toBeVisible();
    await expect(page.getByTestId("tendencias-table")).toBeVisible();
    await expect(page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_CRECIENTE}`)).toBeVisible();

    const fila = page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_CRECIENTE}`);
    await expect(fila).toContainText("Prod Creciente");
    await expect(page.getByTestId(`tendencia-variacion-${MOCK_TENDENCIA_CRECIENTE}`)).toHaveText("+2");
    await expect(page.getByTestId(`tendencia-interpretacion-${MOCK_TENDENCIA_CRECIENTE}`)).toHaveText(
      "Creciente",
    );
    await expect(fila).toContainText("01-04-2026 - 05-04-2026");
  });
});

test.describe("TC06.1 — Panel y tabla de tendencias", () => {
  test("TC06.1 — panel Detalle de tendencias lineales y columnas operativas", async ({ page }) => {
    await gotoDashboardWithMocks(page);

    const panel = page.getByTestId("tendencias-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByText("Detalle de tendencias lineales")).toBeVisible();
    await expect(page.getByTestId("tendencias-table")).toBeVisible();
    await expect(page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_ESTABLE}`)).toBeVisible();

    const fila = page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_ESTABLE}`);
    await expect(page.getByTestId(`tendencia-producto-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText(
      "Prod Estable",
    );
    await expect(page.getByTestId(`tendencia-stock-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText(
      "15 / mín. 10",
    );
    await expect(page.getByTestId(`tendencia-variacion-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText("+0");
    await expect(page.getByTestId(`tendencia-prediccion-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText("20");
    await expect(page.getByTestId(`tendencia-sugerido-${MOCK_TENDENCIA_ESTABLE}`)).toHaveText(
      "Stock suficiente",
    );
    await expect(fila).toBeVisible();

    await page.getByTestId(`corrida-row-${MOCK_CORRIDA_SIN_TENDENCIAS}`).click();
    await expect(page.getByTestId("tendencias-sin-resultados")).toBeVisible();

    await page.getByTestId(`corrida-row-${MOCK_CORRIDA_CON_TENDENCIAS}`).click();
    await expect(page.getByTestId("tendencias-table")).toBeVisible();
    await expect(page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_DECRECIENTE}`)).toBeVisible();
  });
});

test.describe("TC06.2 — Gráfico de línea por producto", () => {
  test("TC06.2 — gráfico con histórico, tendencia y predicción", async ({ page }) => {
    await gotoDashboardWithMocks(page);

    const visualRequest = page.waitForRequest((req) =>
      req.url().includes(`/etl/tendencias/${MOCK_TENDENCIA_CRECIENTE}/visual/`),
    );
    await page.getByTestId(`tendencia-row-${MOCK_TENDENCIA_CRECIENTE}`).click();
    await visualRequest;

    const visualPanel = page.getByTestId("tendencias-visual-panel");
    await expect(visualPanel).toBeVisible();
    await expect(page.getByTestId("tendencia-chart")).toBeVisible();
    await expect(page.getByTestId("tendencia-chart").locator("canvas")).toBeVisible();

    await expect(page.getByTestId("tendencias-prediccion-texto")).toContainText(
      /predicción día siguiente/i,
    );
    await expect(page.getByTestId("tendencias-prediccion-texto")).toContainText(/\d+\s*unidades/i);
    await expect(page.getByTestId("tendencias-visual-titulo")).toContainText("Producto Alfa");

    await expect(visualPanel).not.toContainText("undefined");
    await expect(visualPanel).not.toContainText("NaN");
  });
});

test.describe("TC06.3 — Mensaje de datos insuficientes", () => {
  test("TC06.3 — sin gráfico cuando el detalle visual es insuficiente", async ({ page }) => {
    const config: AnalyticsVisualMockConfig = {
      corridas: [
        buildCorrida({
          id: MOCK_CORRIDA_CON_TENDENCIAS,
          resultados_tendencia_count: 1,
          productos_candidatos_tendencia: 1,
        }),
      ],
      tendenciasByCorrida: {
        [MOCK_CORRIDA_CON_TENDENCIAS]: [
          buildTendencia({
            id: MOCK_TENDENCIA_VISUAL_INSUF,
            pendiente: 0,
            producto_nombre: "Prod Insuficiente",
          }),
        ],
      },
      visualByTendenciaId: {
        [MOCK_TENDENCIA_VISUAL_INSUF]: buildVisualInsufficient(MOCK_TENDENCIA_VISUAL_INSUF),
      },
    };

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await gotoDashboardWithMocks(page, config);

    await expect(page.getByTestId("insufficient-data-message")).toBeVisible();
    await expect(page.getByTestId("insufficient-data-message")).toContainText(
      "datos suficientes",
    );
    await expect(page.getByTestId("tendencia-chart")).toHaveCount(0);

    const critical = consoleErrors.filter(
      (t) => !t.includes("favicon") && !t.toLowerCase().includes("404"),
    );
    expect(critical).toEqual([]);
    await expectNoBrokenUiText(page);
  });
});

test.describe("TC07.2 — Selección de corrida actualiza panel predictivo", () => {
  test("TC07.2 — conteo de tendencias y actualización del panel", async ({ page }) => {
    const config: AnalyticsVisualMockConfig = {
      corridas: [
        buildCorrida({
          id: MOCK_CORRIDA_CON_TENDENCIAS,
          resultados_tendencia_count: 2,
          productos_candidatos_tendencia: 3,
        }),
        buildCorrida({
          id: MOCK_CORRIDA_SIN_TENDENCIAS,
          resultados_tendencia_count: 0,
          productos_candidatos_tendencia: 2,
          fecha_ejecucion: "2026-05-01T10:00:00Z",
        }),
      ],
      tendenciasByCorrida: {
        [MOCK_CORRIDA_CON_TENDENCIAS]: [
          buildTendencia({ id: 301, pendiente: 1, producto_nombre: "Prod A" }),
          buildTendencia({ id: 302, pendiente: -1, producto_nombre: "Prod B" }),
        ],
        [MOCK_CORRIDA_SIN_TENDENCIAS]: [],
      },
      visualByTendenciaId: {
        301: buildVisualOk(301),
        302: buildVisualOk(302),
      },
    };

    await gotoDashboardWithMocks(page, config);

    const filaCon = page.getByTestId(`corrida-row-${MOCK_CORRIDA_CON_TENDENCIAS}`);
    await expect(filaCon).toContainText("2 de 3 productos analizados");
    await expect(page.getByTestId("tendencia-row-301")).toBeVisible();
    await expect(page.getByTestId("tendencia-row-302")).toBeVisible();

    await page.getByTestId(`corrida-row-${MOCK_CORRIDA_SIN_TENDENCIAS}`).click();
    await expect(page.getByTestId("tendencias-sin-resultados")).toBeVisible();
    await expect(page.getByTestId("tendencia-row-301")).toHaveCount(0);

    await filaCon.click();
    await expect(page.getByTestId("tendencias-table")).toBeVisible();
    await expect(page.getByTestId("tendencia-row-301")).toBeVisible();
    await expect(page.getByTestId("tendencia-row-302")).toBeVisible();
  });
});
