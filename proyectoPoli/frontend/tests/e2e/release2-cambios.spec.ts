import { test, expect } from "@playwright/test";
import { E2E_ANALYTICS_USER, E2E_NO_ANALYTICS_USER, E2E_PASSWORD, login } from "./helpers/auth";

/**
 * Pruebas de los últimos cambios del Release 2:
 *  - Filtro de fechas con botón "Filtrar" (draft + commit).
 *  - Tarjeta y tabla de Stock crítico en el dashboard.
 *  - Nueva sección "Análisis integral de consumo" (reemplazo de Hábitos + Demanda vs Consumo).
 *  - Tabs "Análisis inteligente" / "Productos más consumidos del mes".
 *  - Manejo de período sin datos con la nueva sección.
 *  - Re-validación de acceso denegado para usuarios sin permiso.
 *
 * Requisitos: backend en :8000 + `python manage.py create_roles_users` (segupak123 por defecto).
 */
test.describe("Release 2 — autenticación (re-validación)", () => {
  // Smoke test: confirma que las credenciales del usuario analítico siguen siendo válidas.
  test("login del usuario analítico sigue funcionando", async ({ page }) => {
    await login(page, E2E_ANALYTICS_USER, E2E_PASSWORD);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("button", { name: "Cerrar sesión" })).toBeVisible();
  });
});

test.describe("Release 2 — dashboard analítico (cambios recientes)", () => {
  test.beforeEach(async ({ page }) => {
    await login(page, E2E_ANALYTICS_USER, E2E_PASSWORD);
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-page")).toBeVisible();
  });

  // El filtro ahora se aplica recién al hacer click en "Filtrar" (draft + commit).
  test("el botón Filtrar aplica el rango de fechas seleccionado", async ({ page }) => {
    const desde = page.getByTestId("dashboard-fecha-desde");
    const hasta = page.getByTestId("dashboard-fecha-hasta");
    const filtrar = page.getByTestId("dashboard-filtrar");

    await expect(filtrar).toBeVisible();
    await desde.fill("2099-01-01");
    await hasta.fill("2099-01-31");
    await filtrar.click();

    // Tras filtrar, la sección analítica debe seguir cargada (sin error global).
    await expect(page.getByTestId("analytics-dashboard-section")).toBeVisible();
    await expect(page.getByTestId("dashboard-error")).toHaveCount(0);
  });

  // Tarjeta KPI específica de stock crítico (nuevo bloque visible siempre).
  test("tarjeta KPI de stock crítico se muestra en el dashboard", async ({ page }) => {
    const card = page.getByTestId("dashboard-stock-critico-card");
    await expect(card).toBeVisible();
    await expect(card).toContainText("STOCK CRÍTICO");
    await expect(card).toContainText("Sin stock:");
    await expect(card).toContainText("Stock para 7 días o menos:");
  });

  // Sección de stock crítico: tabla con productos o mensaje vacío coherente.
  test("sección de stock crítico muestra tabla o mensaje vacío", async ({ page }) => {
    const seccion = page.getByTestId("dashboard-stock-critico-section");
    await expect(seccion).toBeVisible();
    const tabla = page.getByTestId("dashboard-stock-critico-table");
    const vacio = page.getByTestId("dashboard-stock-critico-empty");
    await expect(tabla.or(vacio)).toBeVisible();
  });

  // La nueva sección "Análisis integral de consumo" reemplaza a "Hábitos de consumo".
  test("sección Análisis integral de consumo está presente en lugar de Hábitos", async ({ page }) => {
    await expect(page.getByTestId("analisis-integral-consumo-section")).toBeVisible();
    // Las testids viejas no deben existir en la nueva versión del dashboard.
    await expect(page.getByTestId("habitos-consumo-section")).toHaveCount(0);
    await expect(page.getByTestId("demanda-vs-consumo-section")).toHaveCount(0);
  });

  // Gráficos mensual y por día de la semana viven dentro de la nueva sección.
  test("gráficos mensual y por día se muestran en Análisis integral", async ({ page }) => {
    await expect(page.getByTestId("analisis-chart-mensual").locator("canvas")).toBeVisible();
    await expect(page.getByTestId("analisis-chart-dia-semana").locator("canvas")).toBeVisible();
  });

  // Tarjetas resumen del período + "Lectura del período" textual.
  test("se muestran tarjetas resumen y la lectura textual del período", async ({ page }) => {
    await expect(page.getByTestId("analisis-resumen-periodo")).toBeVisible();
    const lectura = page.getByTestId("analisis-lectura-periodo");
    await expect(lectura).toBeVisible();
    await expect(lectura).toContainText("Lectura del período");
  });

  // Por defecto el tab "Análisis inteligente" debe estar activo.
  test("tab Análisis inteligente está activo por defecto", async ({ page }) => {
    await expect(page.getByTestId("analisis-tabs")).toBeVisible();
    await expect(page.getByTestId("analisis-tab-inteligente-panel")).toBeVisible();
    await expect(page.getByTestId("analisis-tab-productos-mes-panel")).toHaveCount(0);
  });

  // Cambio de tab a "Productos más consumidos del mes" → muestra tabla del mes.
  test("se puede cambiar al tab Productos más consumidos del mes", async ({ page }) => {
    await page.getByTestId("analisis-tab-productos-mes").click();
    await expect(page.getByTestId("analisis-tab-productos-mes-panel")).toBeVisible();
    await expect(page.getByTestId("analisis-productos-mes-tabla")).toBeVisible();
    await expect(page.getByTestId("analisis-tab-inteligente-panel")).toHaveCount(0);
  });

  // Tab "Análisis inteligente": tabla con filas o mensaje "sin datos suficientes".
  test("tab Análisis inteligente expone tabla o mensaje sin datos", async ({ page }) => {
    await page.getByTestId("analisis-tab-inteligente").click();
    const panel = page.getByTestId("analisis-tab-inteligente-panel");
    await expect(panel).toBeVisible();
    const tabla = page.getByTestId("analisis-inteligente-tabla");
    const empty = page.getByTestId("analisis-inteligente-empty");
    await expect(tabla.or(empty)).toBeVisible({ timeout: 30_000 });
    if (await tabla.isVisible()) {
      await expect(page.getByTestId("analisis-inteligente-resumen")).toBeVisible();
      await expect(page.locator('[data-testid^="analisis-inteligente-row-"]').first()).toBeVisible();
    }
  });

  // Caso sin datos (filtrado a 2099): la sección integral muestra los mensajes vacíos.
  test("período sin movimientos muestra estados vacíos en la sección integral", async ({ page }) => {
    await page.getByTestId("dashboard-fecha-desde").fill("2099-01-01");
    await page.getByTestId("dashboard-fecha-hasta").fill("2099-01-31");
    await page.getByTestId("dashboard-filtrar").click();

    // Banner de analytics sin salidas o gráfico de top vacío como mínimo (puede aparecer cualquiera o ambos).
    await expect(
      page.getByTestId("analytics-no-salidas-banner").or(page.getByTestId("analytics-top-consumidos-empty")).first(),
    ).toBeVisible({ timeout: 30_000 });

    // La sección integral sigue cargando sin error tras cambiar a un período sin movimientos.
    await expect(page.getByTestId("analisis-integral-consumo-section")).toBeVisible();
    await expect(page.getByTestId("analisis-error")).toHaveCount(0);
  });
});

test.describe("Release 2 — control de acceso (re-validación)", () => {
  // Funcionario sigue sin poder ver /api/dashboard/ después de los cambios.
  test("usuario sin permisos sigue viendo el error de acceso al dashboard", async ({ page }) => {
    await login(page, E2E_NO_ANALYTICS_USER, E2E_PASSWORD);
    await page.goto("/dashboard");
    await expect(page.getByTestId("dashboard-error")).toBeVisible();
    await expect(page.getByTestId("dashboard-error")).toContainText("permiso");
    // La nueva sección no debería renderizarse cuando el dashboard reporta error.
    await expect(page.getByTestId("analisis-integral-consumo-section")).toHaveCount(0);
  });
});
