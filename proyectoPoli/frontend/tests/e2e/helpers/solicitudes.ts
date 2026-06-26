import { expect, type Page } from "@playwright/test";
import {
  abrirDetalleSolicitud,
  btnNuevaSolicitud,
  detalleSolicitud,
  gotoSolicitudes,
  solicitudRow,
  testIdOr,
} from "./auth";
import { selectOptionContaining } from "./locators";
import { PRODUCTO_CATALOGO_CON_STOCK } from "./credentials";

function selectTipoProducto(page: Page) {
  return testIdOr(
    page,
    "select-tipo-producto",
    page.locator("select").filter({ has: page.locator('option[value="catalogo"]') }).first(),
  );
}

function selectProductoCatalogo(page: Page) {
  return testIdOr(
    page,
    "select-producto-catalogo",
    page.locator("select").filter({ has: page.locator('option[value=""]') }).nth(1),
  );
}

function inputSolicitante(page: Page) {
  return page.getByPlaceholder("Nombre de quien solicita el insumo");
}

function inputCantidad(page: Page) {
  return testIdOr(page, "input-cantidad", page.getByPlaceholder(/cantidad solicitada/i));
}

function inputDestino(page: Page) {
  return testIdOr(page, "input-destino", page.getByPlaceholder(/área o sector/i));
}

function inputNombreFueraCatalogo(page: Page) {
  return testIdOr(page, "input-nombre-fuera-catalogo", page.getByPlaceholder(/nombre del insumo/i));
}

function inputDescripcion(page: Page) {
  return testIdOr(page, "input-descripcion", page.getByPlaceholder(/detalle/i).first());
}

function btnGuardarSolicitud(page: Page) {
  return testIdOr(page, "btn-guardar-solicitud", page.getByRole("button", { name: /enviar solicitud/i }));
}

export interface SolicitudCreada {
  id: number;
  destino: string;
  cantidad: number;
  productoLabel?: string;
  solicitante?: string;
}

/** Verifica campos visibles en el detalle de una solicitud. */
export async function verificarDetalleSolicitud(
  page: Page,
  opts: {
    producto?: string;
    destino: string;
    cantidad: number | string;
    estado?: RegExp;
    solicitante?: string;
  },
) {
  const detalle = detalleSolicitud(page);
  await expect(detalle).toBeVisible();
  if (opts.producto) await expect(detalle).toContainText(opts.producto);
  await expect(detalle).toContainText(opts.destino);
  await expect(detalle).toContainText(String(opts.cantidad));
  if (opts.estado) await expect(detalle).toContainText(opts.estado);
  if (opts.solicitante) await expect(detalle).toContainText(opts.solicitante);
}

/** Verifica estado visible en listado y detalle. */
export async function verificarEstadoEnListadoYDetalle(
  page: Page,
  solicitudId: number,
  estado: RegExp,
) {
  const detalle = detalleSolicitud(page);
  if (await detalle.isVisible()) {
    await expect(detalle).toContainText(estado);
  }

  if (!(await solicitudRow(page, solicitudId).isVisible())) {
    await gotoSolicitudes(page);
  }
  const row = solicitudRow(page, solicitudId);
  await expect(row).toContainText(estado);

  if (!(await detalle.isVisible())) {
    await abrirDetalleSolicitud(page, solicitudId);
    await expect(detalle).toContainText(estado);
  }
}

/** Crea una solicitud de catálogo y devuelve el id capturado de la respuesta API. */
export async function crearSolicitudCatalogo(
  page: Page,
  opts: { destino: string; cantidad?: number; productoLabel?: string; solicitante?: string },
): Promise<SolicitudCreada> {
  const productoLabel = opts.productoLabel ?? PRODUCTO_CATALOGO_CON_STOCK;
  const cantidad = opts.cantidad ?? 1;

  await gotoSolicitudes(page);
  await btnNuevaSolicitud(page).click();
  if (opts.solicitante) {
    await inputSolicitante(page).fill(opts.solicitante);
  }
  await selectTipoProducto(page).selectOption("catalogo");
  await selectOptionContaining(selectProductoCatalogo(page), productoLabel);
  await inputCantidad(page).fill(String(cantidad));
  await inputDestino(page).fill(opts.destino);

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/purchases/solicitudes/") && r.request().method() === "POST",
  );
  await btnGuardarSolicitud(page).click();
  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()) as { id: number };
  await expect(solicitudRow(page, data.id)).toBeVisible();
  return {
    id: data.id,
    destino: opts.destino,
    cantidad,
    productoLabel,
    solicitante: opts.solicitante,
  };
}

/** Crea una solicitud fuera de catálogo. */
export async function crearSolicitudFueraCatalogo(
  page: Page,
  opts: { nombreProducto: string; destino: string; cantidad?: number; descripcion?: string },
): Promise<SolicitudCreada> {
  const cantidad = opts.cantidad ?? 1;

  await gotoSolicitudes(page);
  await btnNuevaSolicitud(page).click();
  await selectTipoProducto(page).selectOption("fuera");
  await inputNombreFueraCatalogo(page).fill(opts.nombreProducto);
  if (opts.descripcion) {
    await inputDescripcion(page).fill(opts.descripcion);
  }
  await inputCantidad(page).fill(String(cantidad));
  await inputDestino(page).fill(opts.destino);

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/purchases/solicitudes/") && r.request().method() === "POST",
  );
  await btnGuardarSolicitud(page).click();
  const response = await responsePromise;
  expect(response.ok()).toBeTruthy();
  const data = (await response.json()) as { id: number };
  await expect(solicitudRow(page, data.id)).toBeVisible();
  return { id: data.id, destino: opts.destino, cantidad, productoLabel: opts.nombreProducto };
}

/** Compras pasa la solicitud a en revisión. */
export async function comprasPasarARevision(
  page: Page,
  solicitudId: number,
  opts?: { destinoCompra?: "INVENTARIO" | "ENTREGA_INMEDIATA" },
) {
  await gotoSolicitudes(page);
  await abrirDetalleSolicitud(page, solicitudId);
  if (opts?.destinoCompra === "INVENTARIO") {
    await page.getByTestId("destino-compra-inventario").check();
  } else if (opts?.destinoCompra === "ENTREGA_INMEDIATA") {
    await page.getByTestId("destino-compra-entrega").check();
  }
  await page.getByTestId("btn-en-revision").click();
  await expect(detalleSolicitud(page)).toContainText(/revisión|Revisión/i);
}

/** Vincula un ítem fuera de catálogo a un producto del inventario (Compras, post-aprobación Gerencia). */
export async function vincularProductoEnSolicitud(page: Page, productoNombre: string) {
  const select = page.getByTestId("select-vincular-producto");
  await expect(select).toBeVisible({ timeout: 45_000 });
  await selectOptionContaining(select, productoNombre);

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/vincular-detalle/") && r.request().method() === "POST",
  );
  await page.getByTestId("btn-vincular-producto").click();
  expect((await responsePromise).ok()).toBeTruthy();
}
