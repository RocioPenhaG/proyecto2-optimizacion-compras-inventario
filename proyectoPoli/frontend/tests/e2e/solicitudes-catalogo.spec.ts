import { test, expect } from "@playwright/test";
import { abrirDetalleSolicitud, gotoSolicitudes } from "./helpers/auth";
import { AUTH_STATE_PATH, ESTADO_INICIAL_FUNCIONARIO, PRODUCTO_CATALOGO_CON_STOCK } from "./helpers/credentials";
import {
  comprasPasarARevision,
  crearSolicitudCatalogo,
  verificarDetalleSolicitud,
  verificarEstadoEnListadoYDetalle,
} from "./helpers/solicitudes";

/**
 * Solicitudes de catálogo: creación, consulta y flujo de estados con Compras.
 * Excluido: validaciones analíticas, ETL manual, alerta exceso de stock.
 */

test.describe("Creación y consulta (funcionario)", () => {
  test.use({ storageState: AUTH_STATE_PATH.funcionario });

  test("crea solicitud, aparece en listado y detalle con datos principales", async ({ page }) => {
    const destino = `E2E Catálogo ${Date.now()}`;
    const solicitante = `Solicitante E2E ${Date.now()}`;
    const creada = await crearSolicitudCatalogo(page, { destino, cantidad: 1, solicitante });

    const row = page.getByTestId(`solicitud-row-${creada.id}`);
    await expect(row).toContainText(PRODUCTO_CATALOGO_CON_STOCK);
    await expect(row).toContainText(ESTADO_INICIAL_FUNCIONARIO);

    await abrirDetalleSolicitud(page, creada.id);
    await verificarDetalleSolicitud(page, {
      producto: PRODUCTO_CATALOGO_CON_STOCK,
      destino,
      cantidad: 1,
      estado: ESTADO_INICIAL_FUNCIONARIO,
      solicitante,
    });
    await expect(page.getByTestId("detalle-solicitud")).toContainText(/\d{2}\/\d{2}\/\d{4}|\d{4}-\d{2}-\d{2}/);
  });
});

test.describe("Flujo de estados catálogo", () => {
  test.describe.configure({ mode: "serial" });

  const destino = `E2E Flujo Cat ${Date.now()}`;
  let solicitudId = 0;

  test("funcionario crea solicitud", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.funcionario });
    const page = await context.newPage();
    const creada = await crearSolicitudCatalogo(page, { destino, cantidad: 1 });
    solicitudId = creada.id;
    await context.close();
  });

  test("compras pasa a en revisión", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await comprasPasarARevision(page, solicitudId);
    await verificarEstadoEnListadoYDetalle(page, solicitudId, /revisión|Revisión/i);
    await context.close();
  });

  test("compras aprueba solicitud con stock disponible", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await gotoSolicitudes(page);
    await abrirDetalleSolicitud(page, solicitudId);
    await page.getByTestId("btn-aprobar").click();
    await verificarEstadoEnListadoYDetalle(page, solicitudId, /aceptada|Aceptada/i);
    await context.close();
  });

  test("compras finaliza y el estado queda visible", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await gotoSolicitudes(page);
    await abrirDetalleSolicitud(page, solicitudId);
    await page.getByTestId("btn-finalizar").click();
    await expect(page.getByTestId(`solicitud-row-${solicitudId}`)).toContainText(/finalizado|Finalizado/i);
    await abrirDetalleSolicitud(page, solicitudId);
    await expect(page.getByTestId("detalle-solicitud")).toContainText(/finalizado|Finalizado/i);
    await context.close();
  });
});

test.describe("Rechazo con motivo (compras)", () => {
  test.describe.configure({ mode: "serial" });

  let solicitudId = 0;
  const motivo = "E2E rechazo por prueba automatizada";

  test("funcionario crea solicitud para rechazar", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.funcionario });
    const page = await context.newPage();
    const creada = await crearSolicitudCatalogo(page, {
      destino: `E2E Rechazo ${Date.now()}`,
      cantidad: 1,
    });
    solicitudId = creada.id;
    await context.close();
  });

  test("compras rechaza con motivo y el estado se refleja", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await comprasPasarARevision(page, solicitudId);
    await page.getByTestId("input-motivo-rechazo").fill(motivo);
    await page.getByTestId("btn-rechazar").click();
    await verificarEstadoEnListadoYDetalle(page, solicitudId, /rechazada|Rechazada/i);
    await context.close();
  });
});
