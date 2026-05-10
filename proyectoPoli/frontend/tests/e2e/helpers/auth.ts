import { expect, type Page } from "@playwright/test";

/** Credenciales alineadas a `create_roles_users` (por defecto contraseña segupak123). */
export const E2E_ANALYTICS_USER = process.env.E2E_ANALYTICS_USER ?? "compras";
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? "segupak123";
export const E2E_NO_ANALYTICS_USER = process.env.E2E_NO_ANALYTICS_USER ?? "funcionario";

/** Inicia sesión y espera la redirección fuera de /login (necesario para tests que navegan luego). */
export async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-username").fill(username);
  await page.getByTestId("login-password").fill(password);
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/auth/login/") && r.request().method() === "POST"),
    page.getByTestId("login-submit").click(),
  ]);
  await expect(page).not.toHaveURL(/\/login/);
}
