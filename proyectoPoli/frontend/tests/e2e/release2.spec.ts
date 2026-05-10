import { test, expect } from "@playwright/test";
import { E2E_ANALYTICS_USER, E2E_NO_ANALYTICS_USER, E2E_PASSWORD, login } from "./helpers/auth";

test.describe("Release 2 — autenticación", () => {
  // Verifica credenciales contra el backend real (usuario creado con create_roles_users).
  test("login exitoso con usuario de prueba", async ({ page }) => {
    await login(page, E2E_ANALYTICS_USER, E2E_PASSWORD);
    await expect(page.getByRole("button", { name: "Cerrar sesión" })).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });
});

test.describe("Release 2 — dashboard analítico (usuario con permisos)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, E2E_ANALYTICS_USER, E2E_PASSWORD);
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-page")).toBeVisible();
  });

  // Enlace de layout y carga del shell del dashboard.
  test("acceso al dashboard analítico vía navegación", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("nav-dashboard").click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("analytics-dashboard-section")).toBeVisible();
  });

  // Bloque de KPIs materializados por el ETL (total salidas, productos, días, promedio).
  test("visualización de KPIs principales de consumo", async ({ page }) => {
    await expect(page.getByTestId("analytics-kpi-grid")).toBeVisible();
    await expect(page.getByTestId("analytics-kpi-total-salidas")).toBeVisible();
    await expect(page.getByTestId("analytics-kpi-productos-consumo")).toBeVisible();
    await expect(page.getByTestId("analytics-kpi-dias-out")).toBeVisible();
    await expect(page.getByTestId("analytics-kpi-promedio-diario")).toBeVisible();
  });

  // Ranking horizontal de productos más consumidos (Chart.js) o mensaje sin datos.
  test("visualización de productos más consumidos", async ({ page }) => {
    const chartBox = page.getByTestId("analytics-top-consumidos-chart");
    await expect(chartBox).toBeVisible();
    await expect(chartBox.locator("canvas").or(page.getByTestId("analytics-top-consumidos-empty"))).toBeVisible();
  });

  // Análisis integral de consumo: serie mensual agregada (reemplaza Hábitos de consumo).
  test("visualización de gráfico de consumo mensual", async ({ page }) => {
    await expect(page.getByTestId("analisis-chart-mensual").locator("canvas")).toBeVisible();
  });

  // Análisis integral de consumo: distribución por día de la semana (reemplaza Hábitos de consumo).
  test("visualización de consumo por día de la semana", async ({ page }) => {
    await expect(page.getByTestId("analisis-chart-dia-semana").locator("canvas")).toBeVisible();
  });

  // Tabla de corridas registradas por el ETL (vacía o con filas).
  test("visualización del historial de corridas analíticas", async ({ page }) => {
    await expect(page.getByTestId("corridas-etl-section")).toBeVisible();
    await expect(page.getByTestId("corridas-etl-table")).toBeVisible();
    await expect(
      page.getByTestId("corridas-etl-empty").or(page.locator("[data-testid^=\"corrida-row-\"]").first()),
    ).toBeVisible();
  });

  // Panel de tendencias: tabla de coeficientes o mensaje; con datos, gráfico de línea y predicción.
  test("visualización de tendencias lineales", async ({ page }) => {
    await expect(page.getByTestId("tendencias-lineales-panel")).toBeVisible();
    const tabla = page.getByTestId("tendencias-tabla");
    const sinResultados = page.getByTestId("tendencias-sin-resultados");
    const elegir = page.getByTestId("tendencias-sin-corrida");
    const panelVisual = page.getByTestId("tendencias-visual-panel");
    const insuficiente = page.getByTestId("tendencias-visual-insuficiente");
    await expect(tabla.or(sinResultados).or(elegir).or(panelVisual).or(insuficiente)).toBeVisible({
      timeout: 45_000,
    });
    if (await panelVisual.isVisible()) {
      await expect(page.getByTestId("tendencias-chart-linea").locator("canvas")).toBeVisible();
      await expect(page.getByTestId("tendencias-prediccion-texto")).toContainText("Predicción siguiente");
    }
  });

  // Período sin movimientos OUT: avisos coherentes en analítica e integral de consumo.
  test("caso sin datos analíticos disponibles en el período", async ({ page }) => {
    await page.getByTestId("dashboard-fecha-desde").fill("2099-01-01");
    await page.getByTestId("dashboard-fecha-hasta").fill("2099-01-31");
    await page.getByTestId("dashboard-filtrar").click();
    await expect(
      page.getByTestId("analytics-no-salidas-banner").or(page.getByTestId("analytics-top-consumidos-empty")).first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("analisis-sin-datos-periodo")).toBeVisible({ timeout: 30_000 });
  });
});

test.describe("Release 2 — control de acceso", () => {
  // Funcionario no autorizado para /api/dashboard/: mensaje de permiso en la vista.
  test("validación de acceso denegado al dashboard analítico", async ({ page }) => {
    await login(page, E2E_NO_ANALYTICS_USER, E2E_PASSWORD);
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-error")).toBeVisible();
    await expect(page.getByTestId("dashboard-error")).toContainText("permiso");
  });
});
