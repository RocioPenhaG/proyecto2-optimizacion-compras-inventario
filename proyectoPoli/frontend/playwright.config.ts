import { defineConfig, devices } from "@playwright/test";

/**
 * Suite E2E operativa del sistema Segupak.
 * Ejecutar: npm run test:e2e (operativa) | npm run test:e2e:release2 (legacy mocks)
 * Requisitos: backend en http://127.0.0.1:8000, usuarios (`create_roles_users`) y productos (`seed_productos_iniciales`).
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";

/** Archivos legacy con mocks; fuera de la suite operativa principal. */
const LEGACY_SPECS = /release2|analytics-visual/;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: { timeout: 25_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "chromium",
      dependencies: ["setup"],
      testIgnore: [/auth\.setup\.ts/, LEGACY_SPECS],
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.E2E_SKIP_WEBSERVER
    ? undefined
    : {
        command: "npm run dev:e2e",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
