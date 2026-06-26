import { test as setup } from "@playwright/test";
import { login } from "./helpers/auth";
import { AUTH_STATE_PATH, roleCredentials, type E2ERole } from "./helpers/credentials";
/**
 * Genera storageState por rol para reutilizar sesión en la suite operativa.
 * Ejecuta login real contra backend + frontend en ejecución.
 */
const roles: E2ERole[] = ["funcionario", "compras", "gerencia"];

for (const role of roles) {
  setup(`autenticar como ${role}`, async ({ page }) => {
    const creds = roleCredentials[role];
    await login(page, creds.user, creds.pass);
    await page.context().storageState({ path: AUTH_STATE_PATH[role] });
  });
}