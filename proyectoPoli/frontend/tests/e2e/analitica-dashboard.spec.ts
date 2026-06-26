import { test, expect } from "@playwright/test";
import { gotoApp, gotoDashboard, testIdOr } from "./helpers/auth";
import { AUTH_STATE_PATH } from "./helpers/credentials";

/**
 * Dashboard y analítica: KPIs, secciones visibles, filtros y corridas ETL existentes.
 */

test.describe("Dashboard (compras)", () => {
  test.use({ storageState: AUTH_STATE_PATH.compras });

  test("accede al dashboard y cargan KPIs principales", async ({ page }) => {
    await gotoDashboard(page);
    await expect(
      testIdOr(page, "dashboard-periodo-resumen", page.getByText(/periodo|Periodo/i).first()),
    ).toBeVisible();
    await expect(
      testIdOr(page, "dashboard-stock-critico-card", page.getByText(/stock crítico/i).first()),
    ).toBeVisible();
  });

  test("visualiza secciones analíticas existentes", async ({ page }) => {
    await gotoDashboard(page);
    await expect(
      testIdOr(page, "dashboard-analitico", page.getByRole("heading", { name: /consumo|analítica|analisis/i }).first()),
    ).toBeVisible();
    await expect(
      testIdOr(page, "analytics-dashboard-section", page.getByText(/KPI|salidas|consumo/i).first()),
    ).toBeVisible();
    await expect(
      testIdOr(page, "analisis-integral-consumo-section", page.getByText(/análisis integral|analisis integral/i).first()),
    ).toBeVisible();
    await expect(
      testIdOr(page, "corridas-etl-section", page.getByText(/corridas|ETL/i).first()),
    ).toBeVisible();
    await expect(
      testIdOr(page, "tendencias-panel", page.getByText(/tendencias|predicción/i).first()),
    ).toBeVisible();
  });

  test("aplica filtro de periodo disponible", async ({ page }) => {
    await gotoDashboard(page);
    await expect(
      testIdOr(page, "filtros-dashboard", page.getByText(/periodo|filtro/i).first()),
    ).toBeVisible();
    await testIdOr(
      page,
      "analytics-period-select",
      page.locator("select").filter({ has: page.locator('option[value="7d"]') }).first(),
    ).selectOption("7d");
    await expect(
      testIdOr(page, "dashboard-periodo-resumen", page.getByText(/periodo|Periodo/i).first()),
    ).toBeVisible();
    await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  });

  test("muestra corridas ETL registradas o mensaje vacío", async ({ page }) => {
    await gotoDashboard(page);
    await expect(page.getByTestId("corridas-etl-section")).toBeVisible();
    const vacio = page.getByTestId("corridas-etl-empty");
    const filas = page.locator('[data-testid^="corrida-row-"]');
    if ((await vacio.count()) > 0 && (await vacio.isVisible())) {
      await expect(vacio).toContainText(/No hay corridas/i);
    } else {
      await expect(filas.first()).toBeVisible();
      await expect(filas.first().locator("td").first()).not.toBeEmpty();
    }
  });
});

test.describe("Acceso al dashboard por rol", () => {
  test.use({ storageState: AUTH_STATE_PATH.funcionario });

  test("funcionario no ve enlace en menú", async ({ page }) => {
    await gotoApp(page, "/");
    await expect(page.locator("header").getByRole("link", { name: "Dashboard", exact: true })).toHaveCount(0);
  });

  test("funcionario recibe bloqueo al acceder directo", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-error")).toContainText(/permiso|dashboard/i, {
      timeout: 45_000,
    });
  });
});
