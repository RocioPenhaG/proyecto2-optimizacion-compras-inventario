import { expect, type Locator, type Page } from "@playwright/test";

/** Prefer data-testid; use visible fallback when the bundle no tiene testids. */
export function testIdOr(page: Page, testId: string, fallback: Locator): Locator {
  return page.getByTestId(testId).or(fallback).first();
}

export function solicitudesTable(page: Page): Locator {
  return testIdOr(
    page,
    "tabla-solicitudes",
    page.getByRole("table").filter({ hasText: /Estado|Producto|Solicitante/i }).first(),
  );
}

export function btnNuevaSolicitud(page: Page): Locator {
  return testIdOr(page, "btn-nueva-solicitud", page.getByRole("button", { name: /nueva solicitud/i }));
}

export function movimientosTable(page: Page): Locator {
  return testIdOr(
    page,
    "tabla-movimientos",
    page.getByRole("table").filter({ hasText: /Entrada|Salida|Tipo|Producto/i }).first(),
  );
}

export function productosTable(page: Page): Locator {
  return testIdOr(page, "tabla-inventario", page.getByRole("table").first());
}

export function dashboardRoot(page: Page): Locator {
  return page
    .getByTestId("dashboard-page")
    .or(page.getByRole("heading", { name: "Dashboard", exact: true }))
    .first();
}

export function btnRegistrarMovimiento(page: Page): Locator {
  return testIdOr(
    page,
    "btn-registrar-movimiento",
    page.getByRole("button", { name: /registrar movimiento/i }),
  );
}

/** Submit del modal (no confundir con el botón del header que abre el modal). */
export function btnGuardarMovimiento(page: Page): Locator {
  return page
    .getByTestId("btn-guardar-movimiento")
    .or(page.getByTestId("form-movimiento").getByRole("button", { name: /^registrar movimiento$/i }))
    .first();
}

export function solicitudRow(page: Page, id: number): Locator {
  return testIdOr(
    page,
    `solicitud-row-${id}`,
    page.getByRole("row").filter({ hasText: new RegExp(`\\b${id}\\b`) }),
  );
}

export function detalleSolicitud(page: Page): Locator {
  return testIdOr(
    page,
    "detalle-solicitud",
    page.locator("div").filter({ hasText: /Detalle de solicitud|Estado de la solicitud/i }).first(),
  );
}

/** Selecciona una opción de un <select> cuyo texto contiene `texto` (sin depender de label exacto). */
export async function selectOptionContaining(select: Locator, texto: string) {
  const opciones = select.locator("option[value]:not([value=''])");
  await expect(opciones.first()).toBeAttached({ timeout: 45_000 });
  const option = select.locator("option").filter({ hasText: texto }).first();
  await expect(option).toHaveCount(1);
  const value = await option.getAttribute("value");
  if (!value) throw new Error(`No se encontró option con texto "${texto}"`);
  await select.selectOption(value);
}
