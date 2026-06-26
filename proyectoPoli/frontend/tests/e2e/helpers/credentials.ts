/** Credenciales E2E alineadas a los usuarios de prueba del backend. */
const defaultPass = process.env.E2E_PASSWORD ?? "segupak123";

export type E2ERole = "funcionario" | "compras" | "gerencia";

/**
 * Por defecto (suite operativa):
 * - funcionario / gerencia → segupak123
 * - compras → segupak1234
 * Otros usuarios de prueba documentados en additionalTestUsers (informatica, taller, admin).
 * Sobrescribibles con E2E_*_USER y E2E_*_PASS.
 */
export const roleCredentials: Record<E2ERole, { user: string; pass: string }> = {
  funcionario: {
    user: process.env.E2E_FUNCIONARIO_USER ?? "funcionario",
    pass: process.env.E2E_FUNCIONARIO_PASS ?? defaultPass,
  },
  compras: {
    user: process.env.E2E_COMPRAS_USER ?? "compras",
    pass: process.env.E2E_COMPRAS_PASS ?? "segupak1234",
  },
  gerencia: {
    user: process.env.E2E_GERENCIA_USER ?? "gerencia",
    pass: process.env.E2E_GERENCIA_PASS ?? defaultPass,
  },
};

export const AUTH_STATE_PATH: Record<E2ERole, string> = {
  funcionario: "playwright/.auth/funcionario.json",
  compras: "playwright/.auth/compras.json",
  gerencia: "playwright/.auth/gerencia.json",
};

/** Producto con stock del seed inicial, usado en flujos de catálogo. */
export const PRODUCTO_CATALOGO_CON_STOCK = "Pilas AA";

/** Etiqueta visible del estado SOLICITADO para el rol funcionario en la UI. */
export const ESTADO_INICIAL_FUNCIONARIO = /enviado|Enviado/i;

/**
 * Usuarios adicionales del entorno de pruebas (referencia manual / pruebas futuras).
 * No forman parte de auth.setup ni de la suite operativa por defecto.
 */
export const additionalTestUsers = {
  informatica: {
    user: process.env.E2E_INFORMATICA_USER ?? "informatica",
    pass: process.env.E2E_INFORMATICA_PASS ?? "segupak1234",
  },
  taller: {
    user: process.env.E2E_TALLER_USER ?? "taller",
    pass: process.env.E2E_TALLER_PASS ?? "segupak1234",
  },
  admin: {
    user: process.env.E2E_ADMIN_USER ?? "admin",
    pass: process.env.E2E_ADMIN_PASS ?? "segupak1234",
  },
} as const;

