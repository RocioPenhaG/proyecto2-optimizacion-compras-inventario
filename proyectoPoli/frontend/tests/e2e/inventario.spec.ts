import { test, expect } from "@playwright/test";
import { gotoDashboard, gotoInventario, gotoProductos, testIdOr } from "./helpers/auth";
import { btnRegistrarMovimiento, btnGuardarMovimiento, movimientosTable, productosTable, selectOptionContaining } from "./helpers/locators";
import { AUTH_STATE_PATH, PRODUCTO_CATALOGO_CON_STOCK } from "./helpers/credentials";

/**
 * Inventario y movimientos: registro manual IN/OUT, columnas de la tabla y stock crítico.
 */

async function stockVisibleEnProductos(page: import("@playwright/test").Page, producto: string) {
  await gotoProductos(page);
  const fila = productosTable(page).locator("tbody tr").filter({ hasText: producto });
  await expect(fila.first()).toBeVisible();
  await expect(fila.first()).toContainText(/\d+/);
}

function selectTipoMovimiento(page: import("@playwright/test").Page) {
  return testIdOr(page, "select-tipo-movimiento", page.locator("form select").first());
}

function inputCantidadMovimiento(page: import("@playwright/test").Page) {
  return testIdOr(page, "input-cantidad-movimiento", page.locator('form input[type="number"]').first());
}

function selectProductoMovimiento(page: import("@playwright/test").Page) {
  return testIdOr(page, "select-producto-movimiento", page.locator("form select").nth(1));
}

test.describe("Movimientos manuales", () => {
  test.use({ storageState: AUTH_STATE_PATH.compras });

  test("registra entrada manual de stock", async ({ page }) => {
    await gotoInventario(page);
    await btnRegistrarMovimiento(page).click();
    await selectTipoMovimiento(page).selectOption("IN");
    await inputCantidadMovimiento(page).fill("1");
    await selectOptionContaining(selectProductoMovimiento(page), PRODUCTO_CATALOGO_CON_STOCK);

    const responsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/inventory/movimientos/") && r.request().method() === "POST",
    );
    await btnGuardarMovimiento(page).click();
    expect((await responsePromise).ok()).toBeTruthy();

    await expect(movimientosTable(page)).toContainText(/Entrada/i);
    await stockVisibleEnProductos(page, PRODUCTO_CATALOGO_CON_STOCK);
  });

  test("registra salida manual cuando hay stock", async ({ page }) => {
    await gotoInventario(page);
    await btnRegistrarMovimiento(page).click();
    await selectTipoMovimiento(page).selectOption("OUT");
    await inputCantidadMovimiento(page).fill("1");
    await selectOptionContaining(selectProductoMovimiento(page), PRODUCTO_CATALOGO_CON_STOCK);

    const responsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/inventory/movimientos/") && r.request().method() === "POST",
    );
    await btnGuardarMovimiento(page).click();
    expect((await responsePromise).ok()).toBeTruthy();

    await page.locator("#buscar-producto-mov").fill(PRODUCTO_CATALOGO_CON_STOCK);
    await page.waitForTimeout(500);
    const fila = movimientosTable(page).locator("tbody tr").first();
    await expect(fila).toContainText(PRODUCTO_CATALOGO_CON_STOCK);
    await expect(fila).toContainText(/Salida/i);
  });

  test("tabla muestra producto, cantidad, tipo, fecha y responsable", async ({ page }) => {
    await gotoInventario(page);
    const fila = movimientosTable(page).locator("tbody tr").first();
    await expect(fila).toBeVisible();
    await expect(fila.locator("td").nth(0)).not.toBeEmpty();
    await expect(fila.locator("td").nth(1)).toContainText(/Entrada|Salida|Ajuste/i);
    await expect(fila.locator("td").nth(2)).not.toBeEmpty();
    await expect(fila.locator("td").nth(3)).toContainText(/\d/);
    await expect(fila.locator("td").nth(4)).not.toBeEmpty();
  });
});

test.describe("Stock crítico (UI existente)", () => {
  test.use({ storageState: AUTH_STATE_PATH.compras });

  test("dashboard muestra tarjeta de stock crítico", async ({ page }) => {
    await gotoDashboard(page);
    await expect(page.getByTestId("dashboard-stock-critico-card")).toBeVisible();
  });

  test("productos muestran indicador crítico cuando corresponde", async ({ page }) => {
    await gotoProductos(page);
    const criticos = page.getByTestId("alerta-stock-critico");
    if ((await criticos.count()) > 0) {
      await expect(criticos.first()).toContainText("Crítico");
    }
  });
});
