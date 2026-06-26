import { expect, type Locator, type Page } from "@playwright/test";
import { roleCredentials } from "./credentials";
import {
  btnNuevaSolicitud,
  dashboardRoot,
  detalleSolicitud,
  movimientosTable,
  productosTable,
  solicitudesTable,
  solicitudRow,
  testIdOr,
} from "./locators";

export { btnNuevaSolicitud, detalleSolicitud, solicitudRow, testIdOr };

/** Botón de cerrar sesión (testid preferido; fallback por texto accesible). */
export function logoutButton(page: Page): Locator {
  return page
    .getByTestId("btn-logout")
    .or(page.getByRole("button", { name: /cerrar sesión/i }));
}

/** Enlace de navegación principal (testid preferido; fallback por nombre visible). */
export function navLink(page: Page, testId: string, name: string | RegExp): Locator {
  const header = page.locator("header");
  const exact = typeof name === "string";
  return header.getByTestId(testId).or(header.getByRole("link", { name, exact }));
}

/** Credenciales legacy para pruebas de release/analítica con mocks. */
export const E2E_ANALYTICS_USER = process.env.E2E_ANALYTICS_USER ?? "compras";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? roleCredentials.compras.pass;
export const E2E_NO_ANALYTICS_USER = process.env.E2E_NO_ANALYTICS_USER ?? "funcionario";

async function loginFailureMessage(
  page: Page,
  username: string,
  response: import("@playwright/test").APIResponse | null,
): Promise<string> {
  const parts: string[] = [`Login falló para usuario "${username}".`];

  if (response) {
    let apiDetail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") apiDetail = body.detail;
      else if (body.detail != null) apiDetail = JSON.stringify(body.detail);
    } catch {
      apiDetail = await response.text().catch(() => "");
    }
    if (apiDetail) parts.push(`API (${response.status()}): ${apiDetail}`);
    else parts.push(`API respondió ${response.status()}.`);
  }

  const errorEl = page.getByTestId("login-error");
  if (await errorEl.isVisible().catch(() => false)) {
    const uiError = (await errorEl.textContent())?.trim();
    if (uiError) parts.push(`UI: ${uiError}`);
  }

  if (parts.length === 1) {
    parts.push("Permanece en /login sin mensaje visible en el formulario.");
  }

  parts.push(
    "Credenciales E2E por defecto: funcionario/gerencia → segupak123; compras → segupak1234 (E2E_* para sobrescribir).",
  );
  return parts.join(" | ");
}

/** Espera a que AuthContext termine y el layout principal esté visible. */
export async function waitForAppShell(page: Page) {
  await expect(page.getByText("Cargando…", { exact: true })).toBeHidden({ timeout: 45_000 }).catch(() => {});
  await expect(logoutButton(page)).toBeVisible({ timeout: 45_000 });
}

/** Navega a una ruta autenticada y espera el layout. */
export async function gotoApp(page: Page, path: string) {
  await page.goto(path);
  if (/\/login/.test(page.url())) return;
  await waitForAppShell(page);
}

/** Navega al dashboard y espera que termine de cargar (no quede en "Cargando dashboard…"). */
export async function gotoDashboard(page: Page) {
  await page.goto("/dashboard");
  await waitForAppShell(page);
  await expect(dashboardRoot(page)).toBeVisible({ timeout: 60_000 });
}

/** Navega a solicitudes y espera el listado. */
export async function gotoSolicitudes(page: Page) {
  const productsLoaded = page.waitForResponse(
    (r) => r.url().includes("/api/products/productos/") && r.request().method() === "GET" && r.ok(),
  );
  await gotoApp(page, "/solicitudes");
  await productsLoaded.catch(() => {});
  await expect(solicitudesTable(page)).toBeVisible({ timeout: 45_000 });
}

/** Navega a inventario y espera la tabla de movimientos. */
export async function gotoInventario(page: Page) {
  const productsLoaded = page.waitForResponse(
    (r) => r.url().includes("/api/products/productos/") && r.request().method() === "GET" && r.ok(),
  );
  await gotoApp(page, "/inventory");
  await productsLoaded.catch(() => {});
  await expect(movimientosTable(page)).toBeVisible({ timeout: 45_000 });
}

/** Navega a productos y espera la tabla. */
export async function gotoProductos(page: Page) {
  await gotoApp(page, "/products");
  await expect(productosTable(page)).toBeVisible({ timeout: 45_000 });
}

/** Inicia sesión y espera la redirección fuera de /login. */
export async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-username").fill(username);
  await page.getByTestId("login-password").fill(password);

  const responsePromise = page.waitForResponse(
    (r) => r.url().includes("/api/auth/login/") && r.request().method() === "POST",
  );
  await page.getByTestId("login-submit").click();
  const response = await responsePromise;

  const navigated = await page
    .waitForURL((url) => !/\/login/.test(url.pathname), { timeout: 15_000 })
    .then(() => true)
    .catch(() => false);

  if (!navigated || !response.ok()) {
    throw new Error(await loginFailureMessage(page, username, response));
  }

  await waitForAppShell(page);
}

/** Cierra sesión desde el layout principal. */
export async function logout(page: Page) {
  await waitForAppShell(page);
  await logoutButton(page).click();
  await expect(page).toHaveURL(/\/login/);
}

/** Abre el detalle de una solicitud por id desde el listado. */
export async function abrirDetalleSolicitud(page: Page, solicitudId: number) {
  const row = solicitudRow(page, solicitudId);
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Ver" }).click();
  await expect(detalleSolicitud(page)).toBeVisible();
}
