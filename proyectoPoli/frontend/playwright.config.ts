import { defineConfig, devices } from "@playwright/test";

/**
 * E2E del Release 2 (dashboard analítico, hábitos, corridas ETL, tendencias).
 * Requisitos: backend Django en http://127.0.0.1:8000 (proxy de Vite) y usuarios de prueba
 * (`python manage.py create_roles_users`, contraseña por defecto segupak123).
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 20_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: process.env.CI ? "retain-on-failure" : "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.E2E_SKIP_WEBSERVER
    ? undefined
    : {
        // Puerto fijo: si 5173 está libre, Vite arranca ahí; si ya hay servidor, se reutiliza.
        // Sin strictPort, Vite pasa a 5174 y Playwright hace timeout en 5173 (exit code 1).
        command: "npm run dev:e2e",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
