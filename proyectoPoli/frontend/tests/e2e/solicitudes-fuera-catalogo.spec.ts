import { test, expect } from "@playwright/test";
import { abrirDetalleSolicitud, gotoSolicitudes } from "./helpers/auth";
import { AUTH_STATE_PATH, ESTADO_INICIAL_FUNCIONARIO, PRODUCTO_CATALOGO_CON_STOCK } from "./helpers/credentials";
import {
  comprasPasarARevision,
  crearSolicitudFueraCatalogo,
  verificarDetalleSolicitud,
  verificarEstadoEnListadoYDetalle,
  vincularProductoEnSolicitud,
} from "./helpers/solicitudes";

/**
 * Solicitudes fuera de catálogo: flujo Compras → Gerencia → vincular → finalizar.
 * Usa el flujo de entrega inmediata ya implementado en el sistema.
 */

test.describe("Creación fuera de catálogo (funcionario)", () => {
  test.use({ storageState: AUTH_STATE_PATH.funcionario });

  test("crea solicitud visible en listado y detalle", async ({ page }) => {
    const nombre = `Insumo E2E ${Date.now()}`;
    const destino = `Área E2E ${Date.now()}`;
    const creada = await crearSolicitudFueraCatalogo(page, {
      nombreProducto: nombre,
      destino,
      cantidad: 2,
      descripcion: "Prueba E2E fuera de catálogo",
    });

    await expect(page.getByTestId(`solicitud-row-${creada.id}`)).toContainText(nombre);
    await expect(page.getByTestId(`solicitud-row-${creada.id}`)).toContainText(ESTADO_INICIAL_FUNCIONARIO);

    await abrirDetalleSolicitud(page, creada.id);
    await verificarDetalleSolicitud(page, {
      producto: nombre,
      destino,
      cantidad: 2,
      estado: ESTADO_INICIAL_FUNCIONARIO,
    });
  });
});

test.describe("Flujo completo fuera de catálogo", () => {
  test.describe.configure({ mode: "serial" });

  const nombreProducto = `E2E Fuera Cat ${Date.now()}`;
  let solicitudId = 0;

  test("funcionario crea solicitud fuera de catálogo", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.funcionario });
    const page = await context.newPage();
    const creada = await crearSolicitudFueraCatalogo(page, {
      nombreProducto,
      destino: `Destino E2E ${Date.now()}`,
      cantidad: 1,
    });
    solicitudId = creada.id;
    await context.close();
  });

  test("compras revisa y envía a Gerencia", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await comprasPasarARevision(page, solicitudId, { destinoCompra: "ENTREGA_INMEDIATA" });
    await verificarEstadoEnListadoYDetalle(page, solicitudId, /revisión|Revisión/i);
    await context.close();
  });

  test("gerencia valida y aprueba la solicitud", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.gerencia });
    const page = await context.newPage();
    await gotoSolicitudes(page);
    await abrirDetalleSolicitud(page, solicitudId);
    await page.getByTestId("btn-aprobar").click();
    await verificarEstadoEnListadoYDetalle(page, solicitudId, /aceptada|Aceptada/i);
    await context.close();
  });

  test("compras vincula producto y finaliza", async ({ browser }) => {
    const context = await browser.newContext({ storageState: AUTH_STATE_PATH.compras });
    const page = await context.newPage();
    await gotoSolicitudes(page);
    await abrirDetalleSolicitud(page, solicitudId);

    await vincularProductoEnSolicitud(page, PRODUCTO_CATALOGO_CON_STOCK);
    await page.getByTestId("btn-finalizar").click();

    await expect(page.getByTestId(`solicitud-row-${solicitudId}`)).toContainText(/finalizado|Finalizado/i);
    await abrirDetalleSolicitud(page, solicitudId);
    await expect(page.getByTestId("detalle-solicitud")).toContainText(/finalizado|Finalizado/i);
    await context.close();
  });
});
