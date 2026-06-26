import { test, expect } from "@playwright/test";
import { gotoApp, gotoDashboard, gotoSolicitudes, login, logout, navLink, btnNuevaSolicitud } from "./helpers/auth";
import { AUTH_STATE_PATH, roleCredentials } from "./helpers/credentials";

/**
 * Acceso y roles: login por rol, menú según permisos, logout y rutas protegidas.
 */

test.describe("Login por rol", () => {
  test.describe.configure({ mode: "serial" });

  test("login como funcionario", async ({ page }) => {
    const { user, pass } = roleCredentials.funcionario;
    await login(page, user, pass);
    await expect(navLink(page, "nav-solicitudes", "Solicitudes")).toBeVisible();
    await expect(navLink(page, "nav-inventario", "Inventario")).toHaveCount(0);
    await expect(navLink(page, "nav-dashboard", "Dashboard")).toHaveCount(0);
  });

  test("login como compras", async ({ page }) => {
    const { user, pass } = roleCredentials.compras;
    await login(page, user, pass);
    await expect(navLink(page, "nav-inventario", "Inventario")).toBeVisible();
    await expect(navLink(page, "nav-dashboard", "Dashboard")).toBeVisible();
  });

  test("login como gerencia", async ({ page }) => {
    const { user, pass } = roleCredentials.gerencia;
    await login(page, user, pass);
    await expect(navLink(page, "nav-dashboard", "Dashboard")).toBeVisible();
    await gotoSolicitudes(page);
    await expect(btnNuevaSolicitud(page)).toHaveCount(0);
  });
});

test.describe("Menú según rol (sesión reutilizada)", () => {
  test.describe("Funcionario", () => {
    test.use({ storageState: AUTH_STATE_PATH.funcionario });

    test("ve módulos permitidos", async ({ page }) => {
      await gotoApp(page, "/");
      await expect(navLink(page, "nav-inicio", "Inicio")).toBeVisible();
      await expect(navLink(page, "nav-productos", "Productos")).toBeVisible();
      await expect(navLink(page, "nav-solicitudes", "Solicitudes")).toBeVisible();
      await expect(navLink(page, "nav-inventario", "Inventario")).toHaveCount(0);
      await expect(navLink(page, "nav-dashboard", "Dashboard")).toHaveCount(0);
    });

    test("puede acceder a solicitudes", async ({ page }) => {
      await gotoSolicitudes(page);
      await expect(btnNuevaSolicitud(page)).toBeVisible();
    });

    test("no accede a inventario (redirección)", async ({ page }) => {
      await gotoApp(page, "/inventory");
      await expect(page).toHaveURL(/\/$/);
    });

    test("cierra sesión correctamente", async ({ page }) => {
      await gotoApp(page, "/");
      await logout(page);
      await expect(page.getByTestId("login-page")).toBeVisible();
    });
  });

  test.describe("Compras", () => {
    test.use({ storageState: AUTH_STATE_PATH.compras });

    test("ve inventario y dashboard", async ({ page }) => {
      await gotoApp(page, "/");
      await expect(navLink(page, "nav-inventario", "Inventario")).toBeVisible();
      await expect(navLink(page, "nav-dashboard", "Dashboard")).toBeVisible();
    });
  });

  test.describe("Gerencia", () => {
    test.use({ storageState: AUTH_STATE_PATH.gerencia });

    test("accede al dashboard y consulta solicitudes sin crear", async ({ page }) => {
      await gotoDashboard(page);
      await gotoSolicitudes(page);
      await expect(btnNuevaSolicitud(page)).toHaveCount(0);
    });
  });
});

test("redirige a login si no hay sesión", async ({ page }) => {
  await page.goto("/solicitudes");
  await expect(page).toHaveURL(/\/login/);
});

test("redirige a login al acceder al dashboard sin sesión", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
