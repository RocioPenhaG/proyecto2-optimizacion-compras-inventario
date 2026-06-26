import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAccessToken } from "@/contexts/AuthContext";
import { useAuth } from "@/contexts/AuthContext";
import type { User } from "@/services/api";
import { apiErrorMessage } from "@/utils/apiFetch";
import { roundUnidades } from "@/utils/unitsFormat";

/** Barra final obligatoria: sin ella Django responde 301 y el redirect puede perder Authorization detrás del proxy. */
const API_SOLICITUDES = "/api/purchases/solicitudes/";

type Estado = "SOLICITADO" | "EN_REVISION" | "COMPRA_ACEPTADA" | "COMPRA_RECHAZADA" | "FINALIZADO";
type TipoDestinoCompra = "INVENTARIO" | "ENTREGA_INMEDIATA";
type AccionTransicion = "TOMAR_SOLICITUD" | "SOLICITAR_GERENCIA";
type RolViewer = User["role"] | undefined;

function numeroSolicitudVisible(s: { id: number; numero?: number }): number {
  return s.numero ?? s.id;
}

interface SolicitudListItem {
  id: number;
  /** Número correlativo visible (#1, #2…); se compacta al eliminar solicitudes. */
  numero?: number;
  fecha: string;
  estado: Estado;
  destino: string;
  solicitante_nombre: string;
  observacion: string;
  creado_en: string;
  /** True si todos los ítems están vinculados al inventario (catálogo). */
  en_catalogo?: boolean;
  motivo_rechazo?: string;
  /** True si falta stock en depósito (todas las líneas vinculadas al catálogo). */
  requiere_aprobacion_gerencia?: boolean;
  /** True si el inventario cubre todas las cantidades (camino Compras). */
  stock_cubre_solicitud?: boolean;
  /** True si hay líneas sin producto del catálogo; debe vincularse antes de aprobar. */
  pendiente_vincular_catalogo?: boolean;
  /** True si al crear la solicitud hubo ítems fuera de catálogo. */
  contiene_fuera_catalogo?: boolean;
  /** Nombres de productos solicitados (catálogo o fuera de catálogo). */
  productos_resumen?: string;
  /** False si hay ítems fuera de catálogo (solo Gerencia puede rechazar). */
  compras_puede_rechazar?: boolean;
  tipo_destino_compra?: TipoDestinoCompra;
  tipo_destino_compra_label?: string;
}

interface SolicitudDetalleItem {
  id: number;
  /** Id de producto del catálogo, o null si es descripción libre. */
  producto: number | null;
  producto_nombre: string;
  producto_sku: string;
  descripcion_insumo_solicitado?: string;
  /** Cantidad pedida por el funcionario (inmutable). */
  cantidad_inicial?: number;
  /** Cantidad total a comprar (Compras/Gerencia pueden ajustarla). */
  cantidad: number;
  observacion: string;
}

interface SolicitudFull {
  id: number;
  numero?: number;
  fecha: string;
  estado: Estado;
  destino: string;
  solicitante_nombre: string;
  observacion: string;
  creado_en: string;
  motivo_rechazo?: string;
  detalles: SolicitudDetalleItem[];
  requiere_aprobacion_gerencia?: boolean;
  stock_cubre_solicitud?: boolean;
  pendiente_vincular_catalogo?: boolean;
  contiene_fuera_catalogo?: boolean;
  compras_puede_rechazar?: boolean;
  tipo_destino_compra?: TipoDestinoCompra;
  tipo_destino_compra_label?: string;
}

interface ProductOption {
  id: number;
  sku: string;
  nombre: string;
  unidad: string;
  proveedor_nombre: string | null;
}

type ItemRow = {
  tipo: "catalogo" | "fuera";
  producto_id: string;
  /** Nombre del insumo solicitado (solo fuera de catálogo). */
  nombre_fuera: string;
  descripcion: string;
  tamaño: string;
  unidad: string;
  cantidad: number | "";
};

const UNIDADES_MEDIDA = [
  "UNIDAD",
  "KG",
  "G",
  "LITROS",
  "ML",
  "METROS",
  "CM",
  "M2",
  "CAJA",
  "PAQUETE",
  "PAR",
] as const;

type UnidadMedida = (typeof UNIDADES_MEDIDA)[number];

const UNIDAD_ALIASES: Record<string, UnidadMedida> = {
  UN: "UNIDAD",
  U: "UNIDAD",
  UNID: "UNIDAD",
  UNIDADES: "UNIDAD",
  KGS: "KG",
  KILO: "KG",
  KILOS: "KG",
  GR: "G",
  GRAMO: "G",
  GRAMOS: "G",
  L: "LITROS",
  LT: "LITROS",
  LTS: "LITROS",
  LITRO: "LITROS",
  METRO: "METROS",
  M: "METROS",
  CAJAS: "CAJA",
  PAQUETES: "PAQUETE",
  PARES: "PAR",
  ROLLO: "PAQUETE",
  ROLLOS: "PAQUETE",
};

function normalizeUnidadMedida(raw: string): UnidadMedida {
  const key = (raw || "")
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "");
  if ((UNIDADES_MEDIDA as readonly string[]).includes(key)) {
    return key as UnidadMedida;
  }
  return UNIDAD_ALIASES[key] ?? "UNIDAD";
}

function parseCantidadInput(raw: string): number | "" {
  if (!raw.trim()) return "";
  const n = roundUnidades(raw);
  return n != null && n > 0 ? n : "";
}

function cantidadNumerica(item: ItemRow): number {
  if (typeof item.cantidad === "number" && Number.isFinite(item.cantidad)) {
    return item.cantidad;
  }
  return parseCantidadInput(String(item.cantidad)) || 0;
}

const FORM_BOX =
  "relative bg-white w-full max-w-4xl shadow-xl border border-gray-300 rounded-lg";
const FORM_INNER = "px-6 sm:px-8 py-6 sm:py-8";
const FORM_TITLE = "text-lg sm:text-xl font-bold text-gray-900 tracking-wide";
const FORM_LABEL = "block text-sm font-medium text-gray-700 mb-1";
const FORM_CONTROL =
  "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none";
const FORM_CONTROL_READONLY =
  "block w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-800 min-h-[2.5rem]";
const FORM_DIVIDER = "border-t border-gray-200 my-4";

const ESTADO_LABEL: Record<Estado, string> = {
  SOLICITADO: "Solicitado",
  EN_REVISION: "En revisión",
  COMPRA_ACEPTADA: "Compra aceptada",
  COMPRA_RECHAZADA: "Compra rechazada",
  FINALIZADO: "Finalizado",
};

function estadoDisplayLabel(
  estado: Estado,
  role?: RolViewer,
  contieneFueraCatalogo?: boolean,
): string {
  if (role === "GERENCIA" && (estado === "SOLICITADO" || estado === "EN_REVISION")) {
    return "Nuevo";
  }
  if (estado === "SOLICITADO") {
    if (role === "FUNCIONARIO") return "Enviado";
    if (role === "COMPRAS" || role === "CONTABLE" || role === "ADMINISTRADOR") {
      return "Nuevo";
    }
    return "Enviado";
  }
  if (estado === "COMPRA_ACEPTADA") {
    return contieneFueraCatalogo ? "Compra aceptada" : "Solicitud aceptada";
  }
  if (estado === "COMPRA_RECHAZADA") {
    return contieneFueraCatalogo ? "Compra rechazada" : "Solicitud rechazada";
  }
  return ESTADO_LABEL[estado];
}

function accionInicialCompras(s: { contiene_fuera_catalogo?: boolean }): AccionTransicion {
  return s.contiene_fuera_catalogo ? "SOLICITAR_GERENCIA" : "TOMAR_SOLICITUD";
}

function etiquetaAccionInicialCompras(s: { contiene_fuera_catalogo?: boolean }): string {
  return s.contiene_fuera_catalogo ? "Solicitar aprobación Gerencia" : "Tomar solicitud";
}

/** Solo fondo: resalta pendientes y acciones por gestionar. */
const ESTADO_BADGE_BG: Record<Estado, string> = {
  SOLICITADO: "bg-sky-200",
  EN_REVISION: "bg-amber-400",
  COMPRA_ACEPTADA: "bg-emerald-200",
  COMPRA_RECHAZADA: "bg-red-200",
  FINALIZADO: "bg-gray-200",
};

const TIPO_DESTINO_COMPRA_LABEL: Record<TipoDestinoCompra, string> = {
  INVENTARIO: "Inventario",
  ENTREGA_INMEDIATA: "Entrega inmediata",
};

function esEntregaInmediata(tipo?: TipoDestinoCompra | null): boolean {
  return tipo === "ENTREGA_INMEDIATA";
}

function solicitudUsaDestinoCompra(s: {
  contiene_fuera_catalogo?: boolean;
  pendiente_vincular_catalogo?: boolean;
  detalles?: SolicitudDetalleItem[];
}): boolean {
  return solicitudEsFueraCatalogo(s);
}

function solicitudEsFueraCatalogo(s: {
  contiene_fuera_catalogo?: boolean;
  pendiente_vincular_catalogo?: boolean;
  detalles?: SolicitudDetalleItem[];
}): boolean {
  if (s.contiene_fuera_catalogo) return true;
  if (s.pendiente_vincular_catalogo) return true;
  return (s.detalles ?? []).some((d) => d.producto == null);
}

function puedeEditarDestinoCompraEnDetalle(
  estado: Estado,
  contieneFueraCatalogo?: boolean,
  tipo?: TipoDestinoCompra | null,
  detalles?: SolicitudDetalleItem[],
): boolean {
  if (!solicitudEsFueraCatalogo({ contiene_fuera_catalogo: contieneFueraCatalogo, detalles })) {
    return false;
  }
  if (estado === "SOLICITADO") return true;
  if ((estado === "EN_REVISION" || estado === "COMPRA_ACEPTADA") && !tipo) return true;
  return false;
}

function DestinoCompraBadge({ tipo }: { tipo?: TipoDestinoCompra | null }) {
  if (!tipo) {
    return (
      <span className="px-2 py-0.5 text-xs font-medium rounded bg-amber-100 text-amber-900">
        Pendiente
      </span>
    );
  }
  const label = TIPO_DESTINO_COMPRA_LABEL[tipo];
  const esInmediata = esEntregaInmediata(tipo);
  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium rounded ${
        esInmediata ? "bg-violet-100 text-violet-900" : "bg-slate-100 text-slate-800"
      }`}
      title={
        esInmediata
          ? "Compra puntual para entregar al solicitante; no genera alerta de stock crítico por stock 0."
          : "La compra incrementa el inventario permanente del área de compras."
      }
    >
      {label}
    </span>
  );
}

function EstadoBadge({
  estado,
  role,
  contieneFueraCatalogo,
  className = "",
}: {
  estado: Estado;
  role?: RolViewer;
  contieneFueraCatalogo?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium rounded text-gray-800 ${ESTADO_BADGE_BG[estado]} ${className}`}
    >
      {estadoDisplayLabel(estado, role, contieneFueraCatalogo)}
    </span>
  );
}

function catalogoEnInventario(s: { en_catalogo?: boolean; pendiente_vincular_catalogo?: boolean }): string {
  const enCatalogo = s.en_catalogo ?? !s.pendiente_vincular_catalogo;
  return enCatalogo ? "Sí" : "No";
}

function solicitudPendienteVincular(detalles: SolicitudDetalleItem[]) {
  return detalles.some((d) => d.producto == null);
}

function destinoEsInventario(
  solicitud: { tipo_destino_compra?: TipoDestinoCompra | null },
  destinoDraft?: TipoDestinoCompra | "",
): boolean {
  const destino = solicitud.tipo_destino_compra ?? destinoDraft ?? "";
  return destino === "INVENTARIO";
}

function destinoEsEntregaInmediata(
  solicitud: { tipo_destino_compra?: TipoDestinoCompra | null },
  destinoDraft?: TipoDestinoCompra | "",
): boolean {
  const destino = solicitud.tipo_destino_compra ?? destinoDraft ?? "";
  return destino === "ENTREGA_INMEDIATA";
}

/** Fuera de catálogo y no entrega inmediata: cantidad inicial vs cantidad a comprar (no funcionario). */
function muestraSeparacionCantidadInventario(
  solicitud: {
    contiene_fuera_catalogo?: boolean;
    pendiente_vincular_catalogo?: boolean;
    detalles?: SolicitudDetalleItem[];
    tipo_destino_compra?: TipoDestinoCompra | null;
  },
  destinoDraft?: TipoDestinoCompra | "",
  role?: RolViewer,
): boolean {
  if (role === "FUNCIONARIO") return false;
  if (!solicitudEsFueraCatalogo(solicitud)) return false;
  return !destinoEsEntregaInmediata(solicitud, destinoDraft);
}

function cantidadInicialDetalle(detalle: SolicitudDetalleItem): number {
  return detalle.cantidad_inicial ?? detalle.cantidad;
}

/** Fuera de catálogo + inventario: Compras puede ajustar cantidad antes de vincular. */
function puedeEditarCantidadDetalleFueraCatalogo(
  solicitud: {
    contiene_fuera_catalogo?: boolean;
    pendiente_vincular_catalogo?: boolean;
    detalles?: SolicitudDetalleItem[];
    tipo_destino_compra?: TipoDestinoCompra | null;
    estado: Estado;
  },
  detalle: SolicitudDetalleItem,
): boolean {
  if (detalle.producto != null) return false;
  if (!solicitudEsFueraCatalogo(solicitud)) return false;
  if (solicitud.tipo_destino_compra === "ENTREGA_INMEDIATA") return false;
  if (
    solicitud.tipo_destino_compra != null &&
    solicitud.tipo_destino_compra !== "INVENTARIO"
  ) {
    return false;
  }
  return (
    solicitud.estado === "SOLICITADO" ||
    solicitud.estado === "EN_REVISION" ||
    solicitud.estado === "COMPRA_ACEPTADA"
  );
}

/** Fuera de catálogo: vincular tras aprobación de Gerencia y con destino de compra definido. */
function puedeMostrarVinculoFueraCatalogo(s: {
  contiene_fuera_catalogo?: boolean;
  pendiente_vincular_catalogo?: boolean;
  detalles?: SolicitudDetalleItem[];
  estado: Estado;
  tipo_destino_compra?: TipoDestinoCompra | null;
}): boolean {
  if (!solicitudEsFueraCatalogo(s)) return false;
  if (!s.tipo_destino_compra) return false;
  return s.estado === "COMPRA_ACEPTADA";
}

function bloqueaAprobacionPorVinculoPendiente(s: {
  contiene_fuera_catalogo?: boolean;
  pendiente_vincular_catalogo?: boolean;
  detalles?: SolicitudDetalleItem[];
}): boolean {
  if (s.contiene_fuera_catalogo) return false;
  if (s.pendiente_vincular_catalogo) return true;
  if (!s.detalles) return false;
  return solicitudPendienteVincular(s.detalles);
}

/** Gerencia solo aprueba o rechaza solicitudes fuera de catálogo. */
function gerenciaPuedeDecidirSolicitud(s: {
  contiene_fuera_catalogo?: boolean;
  estado: Estado;
}): boolean {
  return Boolean(s.contiene_fuera_catalogo) && s.estado === "EN_REVISION";
}

/** Compras aprueba o rechaza solicitudes de productos del catálogo. */
function comprasPuedeAprobarRechazarCatalogo(s: {
  contiene_fuera_catalogo?: boolean;
  estado: Estado;
}): boolean {
  return s.estado === "EN_REVISION" && !s.contiene_fuera_catalogo;
}

function catalogoSinStockSuficiente(s: {
  contiene_fuera_catalogo?: boolean;
  stock_cubre_solicitud?: boolean;
}): boolean {
  return !s.contiene_fuera_catalogo && s.stock_cubre_solicitud === false;
}

const MENSAJE_STOCK_INFERIOR_SOLICITADO =
  "El producto seleccionado tiene un stock inferior al solicitado.";

const MENSAJE_STOCK_REGISTRAR_INVENTARIO = `${MENSAJE_STOCK_INFERIOR_SOLICITADO} Registre stock en inventario antes de finalizar.`;

function AvisoStockInsuficienteCatalogo({ className = "" }: { className?: string }) {
  return (
    <p
      className={`text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md p-3 ${className}`}
      role="status"
      data-testid="aviso-stock-insuficiente-catalogo"
    >
      {MENSAJE_STOCK_REGISTRAR_INVENTARIO}
    </p>
  );
}

function mensajePendienteVinculoNoCompras(estado: Estado): string {
  if (estado === "COMPRA_ACEPTADA") {
    return "Pendiente de vinculación al catálogo por Compras.";
  }
  return "Pendiente de decisión de Gerencia.";
}

function formatFechaSolicitud(fecha?: string): string {
  if (fecha) {
    const parsed = new Date(fecha.includes("T") ? fecha : `${fecha}T12:00:00`);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleDateString("es-PY", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    }
    return fecha;
  }
  return new Date().toLocaleDateString("es-PY", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function parseSolicitanteDeclarado(observacion: string, fallback: string): string {
  const match = observacion?.match(/^Solicitante:\s*(.+?)(?:\n|$)/m);
  return match?.[1]?.trim() || fallback;
}

function parseComentarioGerenciaAprobacion(observacion: string): string {
  const match = observacion?.match(/Comentario Gerencia \(aprobación\): (.+)/);
  return match?.[1]?.trim() ?? "";
}

interface DetalleObservacionParsed {
  descripcion: string;
  tamaño: string;
  unidad: string;
}

function parseDetalleObservacion(observacion: string): DetalleObservacionParsed {
  const result: DetalleObservacionParsed = {
    descripcion: "",
    tamaño: "",
    unidad: "",
  };
  if (!observacion?.trim()) return result;

  for (const part of observacion.split(" | ").map((p) => p.trim())) {
    if (part.startsWith("Descripción: ")) {
      result.descripcion = part.slice("Descripción: ".length);
    } else if (part.startsWith("Tamaño: ")) {
      result.tamaño = part.slice("Tamaño: ".length);
    } else if (part.startsWith("Unidad: ")) {
      result.unidad = part.slice("Unidad: ".length);
    } else if (part.startsWith("Medidas: ")) {
      const med = part.slice("Medidas: ".length).trim();
      const match = med.match(/^(.+?)\s+(UNIDAD|KG|G|LITROS|ML|METROS|CM|M2|CAJA|PAQUETE|PAR)$/);
      result.unidad = match ? match[2] : med;
    }
  }
  return result;
}

function proveedorDeDetalle(detalle: SolicitudDetalleItem, products: ProductOption[]): string {
  if (detalle.producto == null) return "Se define al vincular el producto al catálogo";
  const producto = products.find((p) => p.id === detalle.producto);
  return producto?.proveedor_nombre || "Sin proveedor asignado";
}

function etiquetaProductoCatalogo(
  detalle: SolicitudDetalleItem,
  ocultarSku: boolean,
): string {
  if (!detalle.producto_nombre) return "—";
  if (ocultarSku || !detalle.producto_sku) return detalle.producto_nombre;
  return `${detalle.producto_sku} — ${detalle.producto_nombre}`;
}

function ReadonlyField({
  label,
  value,
  required,
}: {
  label: string;
  value: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className={FORM_LABEL}>
        {label}
        {required && (
          <span className="text-red-600 ml-1" aria-hidden>
            *
          </span>
        )}
      </label>
      <div className={FORM_CONTROL_READONLY}>{value?.trim() ? value : "—"}</div>
    </div>
  );
}

function displaySolicitante(user: User | null): string {
  if (!user) return "—";
  const nombre = [user.first_name, user.last_name].filter(Boolean).join(" ");
  return nombre || user.username;
}

function productOptionLabel(product: ProductOption, ocultarSku: boolean): string {
  return ocultarSku ? product.nombre : `${product.sku} — ${product.nombre}`;
}

function buildDetalleObservacion(item: ItemRow): string {
  const parts: string[] = [];
  parts.push(`Unidad: ${normalizeUnidadMedida(item.unidad)}`);
  if (item.tamaño.trim()) parts.push(`Tamaño: ${item.tamaño.trim()}`);
  if (item.descripcion.trim()) parts.push(`Descripción: ${item.descripcion.trim()}`);
  return parts.join(" | ").slice(0, 255);
}

function defaultItem(): ItemRow {
  return {
    tipo: "catalogo",
    producto_id: "",
    nombre_fuera: "",
    descripcion: "",
    tamaño: "",
    unidad: "UNIDAD",
    cantidad: "",
  };
}

function validateNewFormItem(item: ItemRow): string | null {
  if (item.tipo === "catalogo") {
    const pid = parseInt(String(item.producto_id), 10);
    if (!Number.isFinite(pid) || pid <= 0) {
      return "Seleccione un producto del inventario (tipo de producto obligatorio).";
    }
  } else if (!item.nombre_fuera.trim()) {
    return "Indique el nombre del producto fuera de catálogo.";
  }

  const cantidad = cantidadNumerica(item);
  if (cantidad < 1) {
    return "Indique una cantidad mayor a 0 (campo obligatorio).";
  }
  return null;
}

function initialNewForm(solicitante: string) {
  return {
    destino: "",
    solicitante,
    item: defaultItem(),
  };
}

function DestinoCompraSelector({
  value,
  onChange,
  disabled,
}: {
  value: TipoDestinoCompra | "";
  onChange: (v: TipoDestinoCompra) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className={FORM_LABEL}>
        Destino de compra:
        <span className="text-red-600 ml-1" aria-hidden>
          *
        </span>
      </legend>
      <div className="mt-2 space-y-2">
        <label className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer">
          <input
            type="radio"
            name="tipo_destino_compra_detalle"
            value="INVENTARIO"
            data-testid="destino-compra-inventario"
            checked={value === "INVENTARIO"}
            onChange={() => onChange("INVENTARIO")}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium">Para inventario</span>
            <span className="block text-xs text-gray-500">
              El insumo queda en stock con control de mínimo y alertas de reposición.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer">
          <input
            type="radio"
            name="tipo_destino_compra_detalle"
            value="ENTREGA_INMEDIATA"
            data-testid="destino-compra-entrega"
            checked={value === "ENTREGA_INMEDIATA"}
            onChange={() => onChange("ENTREGA_INMEDIATA")}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium">Entrega inmediata</span>
            <span className="block text-xs text-gray-500">
              Compra puntual para entregar al solicitante; sin stock mínimo ni alerta por stock 0.
            </span>
          </span>
        </label>
      </div>
    </fieldset>
  );
}

const SOLICITUDES_PAGE_SIZE = 10;

export function SolicitudesPage() {
  const token = useAccessToken();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const handledReturnRef = useRef(false);
  const [list, setList] = useState<SolicitudListItem[]>([]);
  const [listTotal, setListTotal] = useState(0);
  const [listPage, setListPage] = useState(1);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterEstado, setFilterEstado] = useState<string>("");

  const [showNewModal, setShowNewModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState<SolicitudFull | null>(null);
  const [saving, setSaving] = useState(false);
  const [newForm, setNewForm] = useState(() => initialNewForm(""));
  /** Borrador de cantidad por línea (detalle id → cantidad). */
  const [cantidadDraftByDetalle, setCantidadDraftByDetalle] = useState<Record<number, number>>({});
  /** producto_id elegido por línea al vincular ítems fuera de catálogo (detalle id → id producto). */
  const [vinculoProductoByDetalle, setVinculoProductoByDetalle] = useState<Record<number, string>>({});
  const [comentarioDecision, setComentarioDecision] = useState("");
  const [destinoCompraDraft, setDestinoCompraDraft] = useState<TipoDestinoCompra | "">("");

  const role = user?.role;
  const isFuncionario = role === "FUNCIONARIO";
  const isAdmin = role === "ADMINISTRADOR";
  const isCompras = role === "COMPRAS";
  const isGerencia = role === "GERENCIA";
  const puedeCambiarEstado = isCompras || isGerencia || isAdmin;
  const puedeGestionarInicial = isCompras || isAdmin;
  const puedeFinalizar = isCompras || isAdmin;
  const puedeVincularCatalogo = isCompras || isAdmin;
  const puedeModificarCantidadCompra = isCompras || isGerencia || isAdmin;
  const puedeVerDestinoCompra = isCompras || isGerencia || isAdmin;
  const canVerFiltroEstado = ["COMPRAS", "GERENCIA", "CONTABLE", "ADMINISTRADOR"].includes(role ?? "");
  const canCreateSolicitud =
    role === "FUNCIONARIO" || role === "COMPRAS" || role === "CONTABLE" || isAdmin;

  const fetchList = async (page = listPage) => {
    if (!token) return;
    const params = new URLSearchParams({ page: String(page) });
    if (filterEstado) params.set("estado", filterEstado);
    const res = await fetch(`${API_SOLICITUDES}?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar solicitudes"));
    const data = await res.json();
    if (Array.isArray(data)) {
      setList(data);
      setListTotal(data.length);
    } else {
      setList(data.results ?? []);
      setListTotal(typeof data.count === "number" ? data.count : 0);
    }
  };

  const fetchProducts = async () => {
    if (!token) return;
    const res = await fetch("/api/products/productos/", { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const data = await res.json();
    const raw = Array.isArray(data) ? data : data.results ?? [];
    setProducts(
      raw.map((p: ProductOption) => ({
        id: p.id,
        sku: p.sku,
        nombre: p.nombre,
        unidad: normalizeUnidadMedida(p.unidad || "UNIDAD"),
        proveedor_nombre: p.proveedor_nombre ?? null,
      })),
    );
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setError("Inicie sesión para ver solicitudes.");
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([fetchList(listPage), fetchProducts()])
      .catch((err) => setError(err instanceof Error ? err.message : "Error"))
      .finally(() => setLoading(false));
  }, [token, filterEstado, listPage]);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [listPage]);

  useEffect(() => {
    if (!showDetailModal) {
      setVinculoProductoByDetalle({});
      setCantidadDraftByDetalle({});
      return;
    }
    const drafts: Record<number, number> = {};
    for (const d of showDetailModal.detalles) {
      drafts[d.id] = d.cantidad;
    }
    setCantidadDraftByDetalle(drafts);
  }, [showDetailModal]);

  const fetchSolicitudDetail = async (id: number): Promise<SolicitudFull | null> => {
    if (!token) return null;
    const res = await fetch(`${API_SOLICITUDES}${id}/`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return null;
    return res.json();
  };

  const openDetail = async (id: number) => {
    const data = await fetchSolicitudDetail(id);
    if (data) {
      setComentarioDecision("");
      setDestinoCompraDraft(data.tipo_destino_compra ?? "");
      setShowDetailModal(data);
    }
  };

  const guardarDestinoCompra = async (id: number, tipo: TipoDestinoCompra) => {
    if (!token || !puedeVerDestinoCompra || !showDetailModal || !solicitudEsFueraCatalogo(showDetailModal)) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_SOLICITUDES}${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tipo_destino_compra: tipo }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === "string" ? err.detail : "Error al guardar destino");
      }
      const data = (await res.json()) as SolicitudFull;
      setDestinoCompraDraft(data.tipo_destino_compra ?? "");
      setShowDetailModal(data);
      await fetchList(listPage);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const irACrearProducto = (
    solicitudId: number,
    detalleId: number,
    nombreSugerido: string,
    cantidad: number,
  ) => {
    const params = new URLSearchParams({
      crear: "1",
      solicitud: String(solicitudId),
      detalle: String(detalleId),
    });
    const nombre = nombreSugerido.trim();
    if (nombre) params.set("nombre", nombre);
    if (Number.isFinite(cantidad) && cantidad > 0) params.set("cantidad", String(cantidad));
    const destino =
      showDetailModal?.tipo_destino_compra ||
      destinoCompraDraft ||
      undefined;
    if (destino) params.set("destino_compra", destino);
    setShowDetailModal(null);
    navigate(`/products?${params.toString()}`);
  };

  useEffect(() => {
    if (!token || handledReturnRef.current) return;
    const solicitudId = searchParams.get("solicitud");
    if (!solicitudId) return;
    const id = parseInt(solicitudId, 10);
    if (!Number.isFinite(id) || id <= 0) return;

    handledReturnRef.current = true;
    const detalleId = searchParams.get("detalle");
    const productoId = searchParams.get("producto");

    (async () => {
      const [data] = await Promise.all([fetchSolicitudDetail(id), fetchProducts()]);
      if (data) {
        setComentarioDecision("");
        setDestinoCompraDraft(data.tipo_destino_compra ?? "");
        setShowDetailModal(data);
        if (detalleId && productoId) {
          const detId = parseInt(detalleId, 10);
          const prodId = parseInt(productoId, 10);
          if (
            Number.isFinite(detId) &&
            detId > 0 &&
            Number.isFinite(prodId) &&
            prodId > 0 &&
            puedeMostrarVinculoFueraCatalogo(data) &&
            (isCompras || isAdmin)
          ) {
            setSaving(true);
            try {
              const res = await fetch(`${API_SOLICITUDES}${id}/vincular-detalle/`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ detalle_id: detId, producto_id: prodId }),
              });
              if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(
                  typeof err.detail === "string" ? err.detail : "Error al vincular el producto",
                );
              }
              const linked = (await res.json()) as SolicitudFull;
              setShowDetailModal(linked);
              await fetchList(listPage);
            } catch (e) {
              setVinculoProductoByDetalle({ [detId]: productoId });
              alert(e instanceof Error ? e.message : "Error al vincular");
            } finally {
              setSaving(false);
            }
          } else if (detalleId && productoId) {
            const detId = parseInt(detalleId, 10);
            if (Number.isFinite(detId) && detId > 0) {
              setVinculoProductoByDetalle({ [detId]: productoId });
            }
          }
        }
      }
      setSearchParams({}, { replace: true });
    })();
  }, [token, searchParams, setSearchParams]);

  const eliminarSolicitud = async (id: number) => {
    if (!token || !isAdmin) return;
    const item =
      showDetailModal?.id === id
        ? showDetailModal
        : list.find((s) => s.id === id);
    const numeroVisible = item ? numeroSolicitudVisible(item) : id;
    if (
      !window.confirm(
        `¿Eliminar la solicitud #${numeroVisible}? Esta acción no se puede deshacer.`,
      )
    ) {
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${API_SOLICITUDES}${id}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error(await apiErrorMessage(res, "Error al eliminar la solicitud"));
      }
      if (showDetailModal?.id === id) {
        setShowDetailModal(null);
      }
      await fetchList(listPage);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const changeEstado = async (id: number, estado: Estado, accion?: AccionTransicion) => {
    if (!token || !puedeCambiarEstado) return;
    const solicitudRef =
      showDetailModal?.id === id ? showDetailModal : list.find((s) => s.id === id);
    const esFueraCatalogo = solicitudRef
      ? solicitudEsFueraCatalogo({
          contiene_fuera_catalogo: solicitudRef.contiene_fuera_catalogo,
          pendiente_vincular_catalogo: solicitudRef.pendiente_vincular_catalogo,
        })
      : false;
    const destinoElegido =
      (showDetailModal?.id === id ? destinoCompraDraft : "") ||
      solicitudRef?.tipo_destino_compra;
    if (
      estado === "EN_REVISION" &&
      puedeVerDestinoCompra &&
      esFueraCatalogo &&
      !destinoElegido
    ) {
      alert("Seleccione el destino de compra (inventario o entrega inmediata) antes de continuar.");
      return;
    }
    const comentario = comentarioDecision.trim();
    setSaving(true);
    try {
      const body: {
        estado: Estado;
        motivo_rechazo?: string;
        comentario_decision?: string;
        accion?: AccionTransicion;
        tipo_destino_compra?: TipoDestinoCompra;
      } = { estado };
      if (accion) body.accion = accion;
      if (
        puedeVerDestinoCompra &&
        esFueraCatalogo &&
        destinoElegido &&
        estado === "EN_REVISION"
      ) {
        body.tipo_destino_compra = destinoElegido;
      }
      if (isGerencia && !isAdmin && (estado === "COMPRA_ACEPTADA" || estado === "COMPRA_RECHAZADA")) {
        body.comentario_decision = comentario;
        if (estado === "COMPRA_RECHAZADA") body.motivo_rechazo = comentario;
      } else if (estado === "COMPRA_RECHAZADA" && (isCompras || isAdmin)) {
        body.motivo_rechazo = comentario;
      }
      const res = await fetch(`${API_SOLICITUDES}${id}/`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === "string" ? err.detail : "Error al cambiar estado");
      }
      const data = (await res.json()) as SolicitudFull;
      await fetchList(listPage);
      setComentarioDecision("");
      if (estado === "FINALIZADO") {
        setShowDetailModal(null);
      } else {
        setDestinoCompraDraft(data.tipo_destino_compra ?? "");
        setShowDetailModal(data);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const guardarCantidadDetalle = async (detalleId: number) => {
    if (!token || !showDetailModal || !puedeModificarCantidadCompra) return;
    const detalle = showDetailModal.detalles.find((d) => d.id === detalleId);
    const cantidadInicial = detalle ? cantidadInicialDetalle(detalle) : 1;
    const cantidadParsed = parseCantidadInput(String(cantidadDraftByDetalle[detalleId] ?? ""));
    if (cantidadParsed === "" || cantidadParsed < 1) {
      alert("Indique una cantidad mayor a 0.");
      return;
    }
    if (cantidadParsed < cantidadInicial) {
      alert(
        `La cantidad a comprar no puede ser menor que la cantidad inicial solicitada (${cantidadInicial}).`,
      );
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(
        `${API_SOLICITUDES}${showDetailModal.id}/actualizar-cantidad-detalle/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ detalle_id: detalleId, cantidad: cantidadParsed }),
        },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err.detail === "string" ? err.detail : "Error al actualizar la cantidad",
        );
      }
      const data: SolicitudFull = await res.json();
      setShowDetailModal(data);
      await fetchList(listPage);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const vincularDetalle = async (detalleId: number) => {
    if (!token || !showDetailModal) return;
    const raw = vinculoProductoByDetalle[detalleId] ?? "";
    const productoId = parseInt(String(raw), 10);
    if (!Number.isFinite(productoId) || productoId <= 0) {
      alert("Seleccione un producto del catálogo para vincular.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${API_SOLICITUDES}${showDetailModal.id}/vincular-detalle/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ detalle_id: detalleId, producto_id: productoId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === "string" ? err.detail : "Error al vincular");
      }
      const data: SolicitudFull = await res.json();
      setShowDetailModal(data);
      setVinculoProductoByDetalle((m) => {
        const next = { ...m };
        delete next[detalleId];
        return next;
      });
      await fetchList();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const updateItemField = (field: keyof ItemRow, value: string | number) => {
    setNewForm((f) => {
      const next = { ...f.item, [field]: value };
      if (field === "tipo") {
        next.producto_id = "";
        next.nombre_fuera = "";
        next.descripcion = "";
      }
      if (field === "producto_id" && value) {
        const prod = products.find((p) => String(p.id) === String(value));
        if (prod?.unidad) next.unidad = normalizeUnidadMedida(prod.unidad);
      }
      return { ...f, item: next };
    });
  };

  const submitNew = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token) return;

    const form = e.currentTarget;
    const cantidadInput = form.elements.namedItem("cantidad") as HTMLInputElement | null;
    const unidadInput = form.elements.namedItem("unidad") as HTMLSelectElement | null;
    const it: ItemRow = {
      ...newForm.item,
      cantidad: parseCantidadInput(cantidadInput?.value ?? String(newForm.item.cantidad)),
      unidad: normalizeUnidadMedida(unidadInput?.value ?? newForm.item.unidad),
    };

    const validationError = validateNewFormItem(it);
    if (validationError) {
      alert(validationError);
      return;
    }

    const cantidad = cantidadNumerica(it);
    const observacion = buildDetalleObservacion(it);
    const detalles =
      it.tipo === "catalogo"
        ? [
            {
              producto: parseInt(String(it.producto_id), 10),
              cantidad,
              observacion,
            },
          ]
        : [
            {
              producto: null,
              descripcion_insumo_solicitado: it.nombre_fuera.trim(),
              cantidad,
              observacion,
            },
          ];
    const solicitanteTexto = newForm.solicitante.trim();
    setSaving(true);
    try {
      const res = await fetch(API_SOLICITUDES, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          destino: newForm.destino,
          observacion: solicitanteTexto ? `Solicitante: ${solicitanteTexto}` : "",
          detalles,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        let msg = "Error al crear la solicitud.";
        if (typeof err.detail === "string") msg = err.detail;
        else if (Array.isArray(err.detalles)) msg = err.detalles.join(" ");
        else if (err.detalles) msg = String(err.detalles);
        throw new Error(msg);
      }
      setListPage(1);
      await fetchList(1);
      setShowNewModal(false);
      setNewForm(initialNewForm(displaySolicitante(user)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando solicitudes...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  const totalPages = Math.max(1, Math.ceil(listTotal / SOLICITUDES_PAGE_SIZE));
  const fromIdx = listTotal === 0 ? 0 : (listPage - 1) * SOLICITUDES_PAGE_SIZE + 1;
  const toIdx = Math.min(listPage * SOLICITUDES_PAGE_SIZE, listTotal);

  const newFormItem = newForm.item;
  const newFormItemProduct = products.find((p) => String(p.id) === newFormItem.producto_id);
  const newFormItemProveedor =
    newFormItem.tipo === "catalogo" && newFormItemProduct?.proveedor_nombre
      ? newFormItemProduct.proveedor_nombre
      : "";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-gray-800">Solicitudes de compra</h2>
        <div className="flex items-center gap-3">
          {canVerFiltroEstado && (
            <select
              value={filterEstado}
              onChange={(e) => {
                setFilterEstado(e.target.value);
                setListPage(1);
              }}
              className="rounded border-gray-300 text-sm"
            >
              <option value="">Todos los estados</option>
              {Object.entries(ESTADO_LABEL).map(([v, l]) => (
                <option key={v} value={v}>
                  {v === "SOLICITADO"
                    ? estadoDisplayLabel("SOLICITADO", role)
                    : v === "COMPRA_ACEPTADA"
                      ? "Aceptada"
                      : l}
                </option>
              ))}
            </select>
          )}
          {canCreateSolicitud && (
            <button
              type="button"
              data-testid="btn-nueva-solicitud"
              onClick={() => {
                setNewForm(initialNewForm(displaySolicitante(user)));
                setShowNewModal(true);
              }}
              className="bg-indigo-600 text-white px-4 py-2 rounded shadow hover:bg-indigo-700 transition"
            >
              Nueva solicitud
            </button>
          )}
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200" data-testid="tabla-solicitudes">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">N°</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
              {puedeVerDestinoCompra && (
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Destino compra
                </th>
              )}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Solicitante</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Catálogo</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acciones</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {list.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50" data-testid={`solicitud-row-${s.id}`}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{numeroSolicitudVisible(s)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{s.fecha}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <EstadoBadge
                    estado={s.estado}
                    role={role}
                    contieneFueraCatalogo={s.contiene_fuera_catalogo}
                  />
                </td>
                <td
                  className="px-6 py-4 text-sm text-gray-700 max-w-[14rem] truncate"
                  title={s.productos_resumen || undefined}
                >
                  {s.productos_resumen?.trim() || "—"}
                </td>
                {puedeVerDestinoCompra && (
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {solicitudUsaDestinoCompra(s) ? (
                      <DestinoCompraBadge tipo={s.tipo_destino_compra} />
                    ) : (
                      "—"
                    )}
                  </td>
                )}
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{s.solicitante_nombre}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {catalogoEnInventario(s)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    type="button"
                    onClick={() => openDetail(s.id)}
                    className="text-indigo-600 hover:text-indigo-800 mr-2"
                  >
                    Ver
                  </button>
                  {isAdmin && (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => eliminarSolicitud(s.id)}
                      className="text-red-700 hover:text-red-900 mr-2 disabled:opacity-50"
                    >
                      Eliminar
                    </button>
                  )}
                  {puedeCambiarEstado && (
                    <>
                      {s.estado === "SOLICITADO" && puedeGestionarInicial && (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() =>
                            changeEstado(s.id, "EN_REVISION", accionInicialCompras(s))
                          }
                          className="px-2 py-1 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                        >
                          {etiquetaAccionInicialCompras(s)}
                        </button>
                      )}
                      {s.estado === "EN_REVISION" && isCompras && comprasPuedeAprobarRechazarCatalogo(s) && (
                        <>
                          <button
                            type="button"
                            disabled={
                              saving ||
                              bloqueaAprobacionPorVinculoPendiente(s) ||
                              catalogoSinStockSuficiente(s)
                            }
                            title={
                              catalogoSinStockSuficiente(s)
                                ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                                : bloqueaAprobacionPorVinculoPendiente(s)
                                  ? "Vincule todas las líneas al catálogo antes de aprobar."
                                  : undefined
                            }
                            onClick={() => changeEstado(s.id, "COMPRA_ACEPTADA")}
                            className="text-green-600 hover:text-green-800 mr-2 disabled:opacity-50"
                          >
                            Aprobar
                          </button>
                          <button
                            type="button"
                            disabled={saving || catalogoSinStockSuficiente(s)}
                            title={
                              catalogoSinStockSuficiente(s)
                                ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                                : undefined
                            }
                            onClick={() => changeEstado(s.id, "COMPRA_RECHAZADA")}
                            className="text-red-600 hover:text-red-800 mr-2 disabled:opacity-50"
                          >
                            Rechazar
                          </button>
                        </>
                      )}
                      {s.estado === "EN_REVISION" &&
                        isGerencia &&
                        gerenciaPuedeDecidirSolicitud(s) && (
                          <>
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() => changeEstado(s.id, "COMPRA_ACEPTADA")}
                              className="text-green-600 hover:text-green-800 mr-2 disabled:opacity-50"
                            >
                              Aprobar
                            </button>
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() => changeEstado(s.id, "COMPRA_RECHAZADA")}
                              className="text-red-600 hover:text-red-800 mr-2 disabled:opacity-50"
                            >
                              Rechazar
                            </button>
                          </>
                        )}
                      {s.estado === "EN_REVISION" && isAdmin && (
                        <>
                          <button
                            type="button"
                            disabled={
                              saving ||
                              bloqueaAprobacionPorVinculoPendiente(s) ||
                              catalogoSinStockSuficiente(s)
                            }
                            title={
                              catalogoSinStockSuficiente(s)
                                ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                                : bloqueaAprobacionPorVinculoPendiente(s)
                                  ? "Vincule todas las líneas al catálogo antes de cambiar el estado."
                                  : undefined
                            }
                            onClick={() => changeEstado(s.id, "COMPRA_ACEPTADA")}
                            className="text-green-600 hover:text-green-800 mr-2 disabled:opacity-50"
                          >
                            Aprobar
                          </button>
                          <button
                            type="button"
                            disabled={
                              saving ||
                              bloqueaAprobacionPorVinculoPendiente(s) ||
                              catalogoSinStockSuficiente(s)
                            }
                            title={
                              catalogoSinStockSuficiente(s)
                                ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                                : bloqueaAprobacionPorVinculoPendiente(s)
                                  ? "Vincule todas las líneas al catálogo antes de cambiar el estado."
                                  : undefined
                            }
                            onClick={() => changeEstado(s.id, "COMPRA_RECHAZADA")}
                            className="text-red-600 hover:text-red-800 mr-2 disabled:opacity-50"
                          >
                            Rechazar
                          </button>
                        </>
                      )}
                      {s.estado === "COMPRA_ACEPTADA" && puedeFinalizar && (
                        <button
                          type="button"
                          disabled={
                            saving ||
                            catalogoSinStockSuficiente(s) ||
                            (s.contiene_fuera_catalogo && Boolean(s.pendiente_vincular_catalogo))
                          }
                          title={
                            catalogoSinStockSuficiente(s)
                              ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                              : s.contiene_fuera_catalogo && s.pendiente_vincular_catalogo
                                ? "Vincule todos los ítems fuera de catálogo antes de finalizar."
                                : undefined
                          }
                          onClick={() => changeEstado(s.id, "FINALIZADO")}
                          className="text-blue-600 hover:text-blue-800 disabled:opacity-50"
                        >
                          Finalizar
                        </button>
                      )}
                    </>
                  )}
                </td>
                </tr>
            ))}
            {list.length === 0 && (
              <tr>
                <td colSpan={puedeVerDestinoCompra ? 8 : 7} className="px-6 py-4 text-center text-sm text-gray-500">
                  No hay solicitudes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-sm text-gray-600">
            {listTotal === 0
              ? "Sin solicitudes"
              : `Mostrando ${fromIdx}–${toIdx} de ${listTotal} solicitudes`}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={listPage <= 1}
              onClick={() => setListPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 text-sm font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Anterior
            </button>
            <span className="text-sm text-gray-600 tabular-nums">
              Página {listPage} de {totalPages}
            </span>
            <button
              type="button"
              disabled={listPage >= totalPages}
              onClick={() => setListPage((p) => Math.min(totalPages, p + 1))}
              className="px-3 py-1.5 text-sm font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>

      {/* Modal Nueva solicitud */}
      {showNewModal && (
        <div className="fixed inset-0 bg-gray-600/40 z-50 overflow-y-auto">
          <div className="flex min-h-full items-start justify-center p-4 sm:p-6">
            <div className={`${FORM_BOX} my-4 sm:my-6`}>
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="absolute top-3 right-3 text-sm text-gray-500 hover:text-gray-800 px-2 py-1"
                aria-label="Cerrar formulario"
              >
                Cerrar
              </button>

              <form onSubmit={submitNew} className={FORM_INNER}>
                <header className="border-b border-gray-300 pb-4 mb-5">
                  <h2 className={FORM_TITLE}>SOLICITUD DE INSUMOS</h2>
                </header>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className={FORM_LABEL}>Fecha:</label>
                    <input
                      type="text"
                      readOnly
                      value={formatFechaSolicitud()}
                      className={FORM_CONTROL_READONLY}
                      aria-readonly
                    />
                  </div>
                  <div>
                    <label className={FORM_LABEL}>Solicitante:</label>
                    <input
                      type="text"
                      value={newForm.solicitante}
                      onChange={(e) => setNewForm((f) => ({ ...f, solicitante: e.target.value }))}
                      placeholder="Nombre de quien solicita el insumo"
                      className={FORM_CONTROL}
                    />
                  </div>
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="mb-4">
                  <label className={FORM_LABEL}>
                    Tipo de producto:
                    <span className="text-red-600 ml-1" aria-hidden>
                      *
                    </span>
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <select
                      value={newFormItem.tipo}
                      data-testid="select-tipo-producto"
                      onChange={(e) => updateItemField("tipo", e.target.value as ItemRow["tipo"])}
                      className={FORM_CONTROL}
                      required
                    >
                      <option value="catalogo">Producto del inventario (catálogo)</option>
                      <option value="fuera">Producto fuera de catálogo</option>
                    </select>
                    {newFormItem.tipo === "catalogo" && (
                      <select
                        value={newFormItem.producto_id}
                        data-testid="select-producto-catalogo"
                        onChange={(e) => updateItemField("producto_id", e.target.value)}
                        className={FORM_CONTROL}
                        required
                      >
                        <option value="">Seleccionar producto…</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {productOptionLabel(p, isFuncionario)}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>

                {newFormItem.tipo === "fuera" && (
                  <>
                    <hr className={FORM_DIVIDER} />

                    <div className="mb-4">
                      <label className={FORM_LABEL}>
                        Nombre del producto:
                        <span className="text-red-600 ml-1" aria-hidden>
                          *
                        </span>
                      </label>
                      <input
                        type="text"
                        data-testid="input-nombre-fuera-catalogo"
                        value={newFormItem.nombre_fuera}
                        onChange={(e) => updateItemField("nombre_fuera", e.target.value)}
                        placeholder="Nombre del insumo a solicitar"
                        className={FORM_CONTROL}
                      />
                    </div>
                  </>
                )}

                <hr className={FORM_DIVIDER} />

                <div className="mb-4">
                  <label className={FORM_LABEL}>Descripción:</label>
                  <input
                    type="text"
                    data-testid="input-descripcion"
                    value={newFormItem.descripcion}
                    onChange={(e) => updateItemField("descripcion", e.target.value)}
                    placeholder={
                      newFormItem.tipo === "catalogo"
                        ? "Detalle adicional del producto (opcional)"
                        : "Detalle o características del insumo (opcional)"
                    }
                    className={FORM_CONTROL}
                  />
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="mb-4">
                  <label className={FORM_LABEL}>Tamaño:</label>
                  <input
                    type="text"
                    value={newFormItem.tamaño}
                    onChange={(e) => updateItemField("tamaño", e.target.value)}
                    placeholder="Opcional"
                    className={FORM_CONTROL}
                  />
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className={FORM_LABEL}>
                      Cantidad:
                      <span className="text-red-600 ml-1" aria-hidden>
                        *
                      </span>
                    </label>
                    <input
                      type="number"
                      name="cantidad"
                      data-testid="input-cantidad"
                      min={1}
                      step={1}
                      required
                      value={newFormItem.cantidad}
                      onChange={(e) => {
                        updateItemField("cantidad", parseCantidadInput(e.target.value));
                      }}
                      placeholder="Indique la cantidad solicitada"
                      className={FORM_CONTROL}
                    />
                  </div>
                  <div>
                    <label className={FORM_LABEL}>Unidad:</label>
                    <select
                      name="unidad"
                      value={normalizeUnidadMedida(newFormItem.unidad)}
                      onChange={(e) => updateItemField("unidad", e.target.value)}
                      className={FORM_CONTROL}
                      aria-label="Unidad"
                    >
                      {UNIDADES_MEDIDA.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="mb-4">
                  <label className={FORM_LABEL}>
                    Destino del producto:
                    <span className="text-red-600 ml-1" aria-hidden>
                      *
                    </span>
                  </label>
                  <input
                    type="text"
                    data-testid="input-destino"
                    value={newForm.destino}
                    onChange={(e) => setNewForm((f) => ({ ...f, destino: e.target.value }))}
                    placeholder="Área o sector donde se utilizará el insumo"
                    className={FORM_CONTROL}
                  />
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="mb-4">
                  <label className={FORM_LABEL}>Proveedor:</label>
                  <input
                    type="text"
                    readOnly
                    value={
                      newFormItemProveedor ||
                      (newFormItem.tipo === "catalogo" && newFormItem.producto_id
                        ? "Sin proveedor asignado"
                        : "Se define al vincular el producto al catálogo")
                    }
                    className={FORM_CONTROL_READONLY}
                    aria-readonly
                  />
                </div>

                <hr className={FORM_DIVIDER} />

                <div className="flex justify-center pt-2">
                  <button
                    type="submit"
                    data-testid="btn-guardar-solicitud"
                    disabled={saving}
                    className="px-10 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-md shadow hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {saving ? "Enviando…" : "Enviar Solicitud"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal Detalle — resumen en lectura, mismo orden que el formulario */}
      {showDetailModal && (
        <div className="fixed inset-0 bg-gray-600/40 z-50 overflow-y-auto">
          <div className="flex min-h-full items-start justify-center p-4 sm:p-6">
            <div className={`${FORM_BOX} my-4 sm:my-6 max-h-[92vh] overflow-y-auto`}>
              <div className={FORM_INNER} data-testid="detalle-solicitud">
                <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-300 pb-4 mb-5">
                  <div>
                    <h2 className={FORM_TITLE}>SOLICITUD DE INSUMOS #{numeroSolicitudVisible(showDetailModal)}</h2>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <EstadoBadge
                        estado={showDetailModal.estado}
                        role={role}
                        contieneFueraCatalogo={showDetailModal.contiene_fuera_catalogo}
                      />
                      {puedeVerDestinoCompra && solicitudUsaDestinoCompra(showDetailModal) && (
                        <DestinoCompraBadge tipo={showDetailModal.tipo_destino_compra} />
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setComentarioDecision("");
                      setShowDetailModal(null);
                    }}
                    className="text-sm text-gray-500 hover:text-gray-800 px-2 py-1"
                  >
                    Cerrar
                  </button>
                </header>

                {catalogoSinStockSuficiente(showDetailModal) && (
                  <AvisoStockInsuficienteCatalogo className="mb-5" />
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <ReadonlyField label="Fecha:" value={formatFechaSolicitud(showDetailModal.fecha)} />
                  <ReadonlyField
                    label="Solicitante:"
                    value={parseSolicitanteDeclarado(
                      showDetailModal.observacion,
                      showDetailModal.solicitante_nombre,
                    )}
                  />
                </div>

                {puedeVerDestinoCompra && solicitudUsaDestinoCompra(showDetailModal) && (
                  <>
                    <hr className={FORM_DIVIDER} />
                    {puedeEditarDestinoCompraEnDetalle(
                      showDetailModal.estado,
                      showDetailModal.contiene_fuera_catalogo,
                      showDetailModal.tipo_destino_compra,
                      showDetailModal.detalles,
                    ) ? (
                      <div className="mb-4">
                        <DestinoCompraSelector
                          value={destinoCompraDraft}
                          disabled={saving}
                          onChange={(tipo) => {
                            setDestinoCompraDraft(tipo);
                            void guardarDestinoCompra(showDetailModal.id, tipo);
                          }}
                        />
                        <p className="mt-2 text-xs text-gray-600">
                          {showDetailModal.estado === "SOLICITADO"
                            ? "Defina el destino y luego envíe la solicitud a Gerencia o tómela para gestión."
                            : "Defina el destino antes de vincular el producto al catálogo."}
                        </p>
                      </div>
                    ) : (
                      <>
                        <ReadonlyField
                          label="Destino de compra:"
                          value={
                            showDetailModal.tipo_destino_compra_label ||
                            (showDetailModal.tipo_destino_compra
                              ? TIPO_DESTINO_COMPRA_LABEL[showDetailModal.tipo_destino_compra]
                              : "—")
                          }
                        />
                        {esEntregaInmediata(showDetailModal.tipo_destino_compra) && (
                          <p className="mt-2 text-xs text-violet-800 bg-violet-50 border border-violet-200 rounded-md p-3">
                            <strong>Entrega inmediata:</strong> al crear el producto no se configura stock
                            mínimo; no genera alerta de stock crítico por quedar en 0 tras la entrega.
                          </p>
                        )}
                        {destinoEsInventario(showDetailModal, destinoCompraDraft) && (
                          <p className="mt-2 text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-md p-3">
                            <strong>Para inventario:</strong> en cada ítem verá la cantidad pedida por el
                            funcionario y la cantidad total a comprar. Al finalizar, solo la cantidad inicial
                            se entrega al solicitante; el resto queda en stock. Al crear el producto indique
                            stock mínimo para alertas de reposición.
                          </p>
                        )}
                        {muestraSeparacionCantidadInventario(showDetailModal, destinoCompraDraft, role) &&
                          !destinoEsInventario(showDetailModal, destinoCompraDraft) && (
                          <p className="mt-2 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-md p-3">
                            <strong>Destino pendiente:</strong> defina «Para inventario» si comprará más unidades
                            que las solicitadas; verá cantidad pedida y cantidad a comprar por ítem.
                          </p>
                        )}
                      </>
                    )}
                  </>
                )}

                {showDetailModal.estado === "COMPRA_RECHAZADA" && showDetailModal.motivo_rechazo && (
                  <p className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
                    <strong>Comentario sobre el rechazo:</strong> {showDetailModal.motivo_rechazo}
                  </p>
                )}

                {showDetailModal.estado === "COMPRA_ACEPTADA" &&
                  parseComentarioGerenciaAprobacion(showDetailModal.observacion) && (
                    <p className="mt-4 text-sm text-green-800 bg-green-50 border border-green-200 rounded-md p-3">
                      <strong>Comentario sobre la aprobación:</strong>{" "}
                      {parseComentarioGerenciaAprobacion(showDetailModal.observacion)}
                    </p>
                  )}

                {puedeMostrarVinculoFueraCatalogo(showDetailModal) &&
                  solicitudPendienteVincular(showDetailModal.detalles) &&
                  puedeVincularCatalogo && (
                  <p className="mt-4 text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md p-3">
                    Gerencia aceptó la compra. Cree o seleccione el producto y vincule cada línea.
                    {esEntregaInmediata(showDetailModal.tipo_destino_compra) ? (
                      <>
                        {" "}
                        En <strong>entrega inmediata</strong>, al vincular se registran automáticamente la
                        entrada y la salida por la cantidad solicitada.
                      </>
                    ) : (
                      <>
                        {" "}
                        Use <strong>Ir a productos</strong> si debe dar de alta el ítem en el catálogo.
                      </>
                    )}
                  </p>
                )}

                {showDetailModal.estado === "SOLICITADO" && puedeGestionarInicial && (
                  <p className="mt-4 text-xs text-gray-600">
                    {showDetailModal.contiene_fuera_catalogo
                      ? "Defina el destino de compra y use «Solicitar aprobación Gerencia»."
                      : "Use «Tomar solicitud» para iniciar la gestión."}
                  </p>
                )}

                <hr className={FORM_DIVIDER} />

                {showDetailModal.detalles.map((d, idx) => {
                  const parsed = parseDetalleObservacion(d.observacion);
                  const esCatalogo = d.producto != null;
                  const tipoLabel = esCatalogo
                    ? "Producto del inventario (catálogo)"
                    : "Producto fuera de catálogo";
                  const productoLabel = esCatalogo
                    ? etiquetaProductoCatalogo(d, isFuncionario)
                    : "";

                  return (
                    <div key={d.id}>
                      {idx > 0 && (
                        <p className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
                          Ítem adicional {idx + 1}
                        </p>
                      )}

                      <div className="mb-4">
                        <ReadonlyField label="Tipo de producto:" value={tipoLabel} required />
                        {esCatalogo && (
                          <div className="mt-2">
                            <ReadonlyField label="Producto seleccionado:" value={productoLabel} />
                          </div>
                        )}
                        {puedeVincularCatalogo &&
                          !esCatalogo &&
                          puedeMostrarVinculoFueraCatalogo(showDetailModal) && (
                          <div className="mt-3 flex flex-wrap gap-2 items-center">
                            <select
                              value={vinculoProductoByDetalle[d.id] ?? ""}
                              data-testid="select-vincular-producto"
                              onChange={(e) =>
                                setVinculoProductoByDetalle((m) => ({ ...m, [d.id]: e.target.value }))
                              }
                              className="text-sm rounded-md border border-gray-300 px-2 py-1.5 min-w-[14rem]"
                            >
                              <option value="">Producto a vincular…</option>
                              {products.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.sku} — {p.nombre}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={saving}
                              data-testid="btn-vincular-producto"
                              onClick={() => vincularDetalle(d.id)}
                              className="text-sm px-3 py-1.5 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                            >
                              Vincular
                            </button>
                            <button
                              type="button"
                              disabled={saving}
                              onClick={() =>
                                irACrearProducto(
                                  showDetailModal.id,
                                  d.id,
                                  d.descripcion_insumo_solicitado ?? "",
                                  d.cantidad,
                                )
                              }
                              className="text-sm px-3 py-1.5 border border-blue-600 text-blue-700 rounded-md hover:bg-blue-50 disabled:opacity-50"
                            >
                              Ir a productos
                            </button>
                          </div>
                        )}
                        {!puedeVincularCatalogo && !esCatalogo && (
                          <p className="mt-2 text-xs text-amber-800">
                            {mensajePendienteVinculoNoCompras(showDetailModal.estado)}
                          </p>
                        )}
                      </div>

                      {muestraSeparacionCantidadInventario(showDetailModal, destinoCompraDraft, role) && (
                        <>
                          <hr className={FORM_DIVIDER} />
                          <div className="mb-4 rounded-lg border-2 border-indigo-200 bg-indigo-50/60 p-4 space-y-3">
                            <p className="text-sm font-semibold text-indigo-900">
                              Cantidades: pedido del funcionario vs. compra total
                            </p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div className="rounded-md border border-slate-200 bg-white p-3">
                                <ReadonlyField
                                  label="Cantidad solicitada (funcionario):"
                                  value={String(cantidadInicialDetalle(d))}
                                  required
                                />
                              </div>
                              <div className="rounded-md border border-indigo-200 bg-white p-3">
                                {puedeModificarCantidadCompra &&
                                puedeEditarCantidadDetalleFueraCatalogo(showDetailModal, d) ? (
                                  <div>
                                    <label className={FORM_LABEL}>
                                      Cantidad a comprar:
                                      <span className="text-red-600 ml-1" aria-hidden>
                                        *
                                      </span>
                                    </label>
                                    <div className="flex flex-wrap gap-2 items-center">
                                      <input
                                        type="number"
                                        min={cantidadInicialDetalle(d)}
                                        step={1}
                                        value={cantidadDraftByDetalle[d.id] ?? d.cantidad}
                                        onChange={(e) => {
                                          const parsedQty = parseCantidadInput(e.target.value);
                                          if (typeof parsedQty === "number") {
                                            setCantidadDraftByDetalle((m) => ({
                                              ...m,
                                              [d.id]: parsedQty,
                                            }));
                                          }
                                        }}
                                        className={`${FORM_CONTROL} max-w-[8rem]`}
                                      />
                                      <button
                                        type="button"
                                        disabled={
                                          saving ||
                                          (cantidadDraftByDetalle[d.id] ?? d.cantidad) === d.cantidad
                                        }
                                        onClick={() => guardarCantidadDetalle(d.id)}
                                        className="text-sm px-3 py-1.5 border border-indigo-600 text-indigo-700 rounded-md hover:bg-indigo-50 disabled:opacity-50"
                                      >
                                        Guardar
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <ReadonlyField
                                    label="Cantidad a comprar:"
                                    value={String(d.cantidad)}
                                    required
                                  />
                                )}
                              </div>
                            </div>
                            {d.cantidad > cantidadInicialDetalle(d) ? (
                              <p className="text-xs text-slate-700 bg-white border border-slate-200 rounded px-3 py-2">
                                Al finalizar se entregan{" "}
                                <strong>{cantidadInicialDetalle(d)}</strong> unidades al solicitante;
                                las <strong>{d.cantidad - cantidadInicialDetalle(d)}</strong> restantes
                                quedan en inventario.
                              </p>
                            ) : (
                              <p className="text-xs text-gray-600">
                                Al finalizar se entregará al solicitante la cantidad inicial; puede
                                aumentar la cantidad a comprar para reponer inventario.
                              </p>
                            )}
                          </div>
                        </>
                      )}

                      {!esCatalogo && (
                        <>
                          <hr className={FORM_DIVIDER} />
                          <ReadonlyField
                            label="Nombre del producto:"
                            value={d.descripcion_insumo_solicitado ?? ""}
                            required
                          />
                        </>
                      )}

                      <hr className={FORM_DIVIDER} />
                      <ReadonlyField label="Descripción:" value={parsed.descripcion} />

                      <hr className={FORM_DIVIDER} />
                      <ReadonlyField label="Tamaño:" value={parsed.tamaño} />

                      <hr className={FORM_DIVIDER} />
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                        {!muestraSeparacionCantidadInventario(showDetailModal, destinoCompraDraft, role) && (
                          <ReadonlyField label="Cantidad:" value={String(d.cantidad)} required />
                        )}
                        <ReadonlyField
                          label="Unidad:"
                          value={parsed.unidad ? normalizeUnidadMedida(parsed.unidad) : ""}
                        />
                      </div>

                      {idx === 0 && (
                        <>
                          <hr className={FORM_DIVIDER} />
                          <ReadonlyField label="Destino del producto:" value={showDetailModal.destino} required />
                          <hr className={FORM_DIVIDER} />
                          <ReadonlyField label="Proveedor:" value={proveedorDeDetalle(d, products)} />
                        </>
                      )}

                      {idx < showDetailModal.detalles.length - 1 && (
                        <hr className={`${FORM_DIVIDER} border-gray-400`} />
                      )}
                    </div>
                  );
                })}

                {showDetailModal.estado === "EN_REVISION" &&
                  ((isCompras && comprasPuedeAprobarRechazarCatalogo(showDetailModal)) ||
                    (isGerencia && gerenciaPuedeDecidirSolicitud(showDetailModal)) ||
                    isAdmin) && (
                  <>
                    <hr className={FORM_DIVIDER} />
                    <div>
                      <label className={FORM_LABEL}>Comentario sobre la decisión (opcional):</label>
                      <textarea
                        data-testid="input-motivo-rechazo"
                        value={comentarioDecision}
                        onChange={(e) => setComentarioDecision(e.target.value)}
                        rows={3}
                        placeholder="Observaciones sobre la aprobación o el rechazo, si lo desea."
                        className={FORM_CONTROL}
                      />
                    </div>
                  </>
                )}

                {showDetailModal.estado === "EN_REVISION" && (
                  <p className="mt-4 text-xs text-gray-600">
                    {isGerencia && !isAdmin && !gerenciaPuedeDecidirSolicitud(showDetailModal)
                      ? "Solicitud de catálogo: solo consulta. La aprobación o rechazo corresponde a Compras."
                      : isGerencia && !isAdmin && gerenciaPuedeDecidirSolicitud(showDetailModal)
                        ? "Revise los datos del pedido y apruebe o rechace la solicitud."
                        : showDetailModal.contiene_fuera_catalogo
                          ? "Solicitud con ítems fuera de catálogo: solo Gerencia puede aprobar o rechazar."
                          : catalogoSinStockSuficiente(showDetailModal)
                            ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                            : showDetailModal.pendiente_vincular_catalogo
                              ? "Vincule cada línea al catálogo antes de aprobar."
                              : isCompras || isAdmin
                                ? "Compras puede aprobar o rechazar esta solicitud de catálogo."
                                : ""}
                  </p>
                )}

                {puedeCambiarEstado && (
                  <div className="flex flex-wrap gap-2 pt-4 mt-4 border-t border-gray-300">
                {showDetailModal.estado === "SOLICITADO" && puedeGestionarInicial && (
                  <button
                    type="button"
                    data-testid="btn-en-revision"
                    disabled={saving}
                    onClick={() =>
                      changeEstado(
                        showDetailModal.id,
                        "EN_REVISION",
                        accionInicialCompras(showDetailModal),
                      )
                    }
                    className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                  >
                    {etiquetaAccionInicialCompras(showDetailModal)}
                  </button>
                )}
                {showDetailModal.estado === "EN_REVISION" && isCompras && comprasPuedeAprobarRechazarCatalogo(showDetailModal) && (
                  <>
                    <button
                      type="button"
                      disabled={
                        saving ||
                        bloqueaAprobacionPorVinculoPendiente(showDetailModal) ||
                        catalogoSinStockSuficiente(showDetailModal)
                      }
                      title={
                        catalogoSinStockSuficiente(showDetailModal)
                          ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                          : bloqueaAprobacionPorVinculoPendiente(showDetailModal)
                            ? "Vincule todas las líneas al catálogo antes de aprobar."
                            : undefined
                      }
                      onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                      className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                      data-testid="btn-aprobar"
                    >
                      Aprobar
                    </button>
                    <button
                      type="button"
                      disabled={saving || catalogoSinStockSuficiente(showDetailModal)}
                      title={
                        catalogoSinStockSuficiente(showDetailModal)
                          ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                          : undefined
                      }
                      onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                      className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                      data-testid="btn-rechazar"
                    >
                      Rechazar
                    </button>
                  </>
                )}
                {showDetailModal.estado === "EN_REVISION" &&
                  isGerencia &&
                  gerenciaPuedeDecidirSolicitud(showDetailModal) && (
                    <>
                      <button
                        type="button"
                        disabled={saving}
                        onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                        className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                        data-testid="btn-aprobar"
                      >
                        Aprobar
                      </button>
                      <button
                        type="button"
                        disabled={saving}
                        onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                        className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                        data-testid="btn-rechazar"
                      >
                        Rechazar
                      </button>
                    </>
                  )}
                {showDetailModal.estado === "EN_REVISION" && isAdmin && (
                  <>
                    <button
                      type="button"
                      disabled={
                        saving ||
                        bloqueaAprobacionPorVinculoPendiente(showDetailModal) ||
                        catalogoSinStockSuficiente(showDetailModal)
                      }
                      title={
                        catalogoSinStockSuficiente(showDetailModal)
                          ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                          : bloqueaAprobacionPorVinculoPendiente(showDetailModal)
                            ? "Vincule todas las líneas al catálogo antes de cambiar el estado."
                            : undefined
                      }
                      onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                      className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                    >
                      Aprobar
                    </button>
                    <button
                      type="button"
                      disabled={
                        saving ||
                        bloqueaAprobacionPorVinculoPendiente(showDetailModal) ||
                        catalogoSinStockSuficiente(showDetailModal)
                      }
                      title={
                        catalogoSinStockSuficiente(showDetailModal)
                          ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                          : bloqueaAprobacionPorVinculoPendiente(showDetailModal)
                            ? "Vincule todas las líneas al catálogo antes de cambiar el estado."
                            : undefined
                      }
                      onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                      className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                    >
                      Rechazar
                    </button>
                  </>
                )}
                {showDetailModal.estado === "COMPRA_ACEPTADA" && puedeFinalizar && (
                  <button
                    type="button"
                    disabled={
                      saving ||
                      catalogoSinStockSuficiente(showDetailModal) ||
                      (showDetailModal.contiene_fuera_catalogo &&
                        solicitudPendienteVincular(showDetailModal.detalles))
                    }
                    title={
                      catalogoSinStockSuficiente(showDetailModal)
                        ? MENSAJE_STOCK_REGISTRAR_INVENTARIO
                        : showDetailModal.contiene_fuera_catalogo &&
                            solicitudPendienteVincular(showDetailModal.detalles)
                          ? "Vincule todos los ítems fuera de catálogo antes de finalizar."
                          : undefined
                    }
                    onClick={() => changeEstado(showDetailModal.id, "FINALIZADO")}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                    data-testid="btn-finalizar"
                  >
                    Finalizar
                  </button>
                )}
                {isAdmin && (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => eliminarSolicitud(showDetailModal.id)}
                    className="px-3 py-1.5 bg-red-700 text-white rounded text-sm hover:bg-red-800 disabled:opacity-50"
                  >
                    Eliminar solicitud
                  </button>
                )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
