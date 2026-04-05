import { useEffect, useState } from "react";
import { useAccessToken } from "@/contexts/AuthContext";
import { useAuth } from "@/contexts/AuthContext";
import { apiErrorMessage } from "@/utils/apiFetch";

/** Barra final obligatoria: sin ella Django responde 301 y el redirect puede perder Authorization detrás del proxy. */
const API_SOLICITUDES = "/api/purchases/solicitudes/";

type Estado = "SOLICITADO" | "EN_REVISION" | "COMPRA_ACEPTADA" | "COMPRA_RECHAZADA" | "FINALIZADO";

interface SolicitudListItem {
  id: number;
  fecha: string;
  estado: Estado;
  destino: string;
  solicitante_nombre: string;
  observacion: string;
  creado_en: string;
  cantidad_items: number;
  motivo_rechazo?: string;
  /** True si falta stock en depósito (todas las líneas vinculadas al catálogo). */
  requiere_aprobacion_gerencia?: boolean;
  /** True si el inventario cubre todas las cantidades (camino Compras). */
  stock_cubre_solicitud?: boolean;
  /** True si hay líneas sin producto del catálogo; debe vincularse antes de aprobar. */
  pendiente_vincular_catalogo?: boolean;
}

interface SolicitudDetalleItem {
  id: number;
  /** Id de producto del catálogo, o null si es descripción libre. */
  producto: number | null;
  producto_nombre: string;
  producto_sku: string;
  descripcion_insumo_solicitado?: string;
  cantidad: number;
  observacion: string;
}

interface SolicitudFull {
  id: number;
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
}

interface ProductOption {
  id: number;
  sku: string;
  nombre: string;
}

const ESTADO_LABEL: Record<Estado, string> = {
  SOLICITADO: "Solicitado",
  EN_REVISION: "En revisión",
  COMPRA_ACEPTADA: "Compra aceptada",
  COMPRA_RECHAZADA: "Compra rechazada",
  FINALIZADO: "Finalizado",
};

function solicitudPendienteVincular(detalles: SolicitudDetalleItem[]) {
  return detalles.some((d) => d.producto == null);
}

export function SolicitudesPage() {
  const token = useAccessToken();
  const { user } = useAuth();
  const [list, setList] = useState<SolicitudListItem[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterEstado, setFilterEstado] = useState<string>("");

  const [showNewModal, setShowNewModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState<SolicitudFull | null>(null);
  const [saving, setSaving] = useState(false);
  type ItemRow = {
    tipo: "catalogo" | "fuera";
    producto_id: string;
    descripcion_fuera: string;
    cantidad: number;
    observacion: string;
  };
  const defaultItem = (): ItemRow => ({
    tipo: "catalogo",
    producto_id: "",
    descripcion_fuera: "",
    cantidad: 1,
    observacion: "",
  });
  const [newForm, setNewForm] = useState({
    destino: "",
    observacion: "",
    items: [defaultItem()],
  });
  /** producto_id elegido por línea al vincular ítems fuera de catálogo (detalle id → id producto). */
  const [vinculoProductoByDetalle, setVinculoProductoByDetalle] = useState<Record<number, string>>({});

  const role = user?.role;
  const isAdmin = role === "ADMINISTRADOR";
  const isCompras = role === "COMPRAS";
  const isGerencia = role === "GERENCIA";
  const puedeCambiarEstado = isCompras || isGerencia || isAdmin;
  const puedePasarARevision = isCompras || isAdmin;
  const puedeFinalizar = isCompras || isAdmin;
  const puedeVincularCatalogo = isCompras || isGerencia || isAdmin;
  const canVerFiltroEstado = ["COMPRAS", "GERENCIA", "CONTABLE", "ADMINISTRADOR"].includes(role ?? "");
  const canCreateSolicitud =
    role === "FUNCIONARIO" || role === "COMPRAS" || role === "CONTABLE" || isAdmin;

  const fetchList = async () => {
    if (!token) return;
    const url = filterEstado
      ? `${API_SOLICITUDES}?estado=${encodeURIComponent(filterEstado)}`
      : API_SOLICITUDES;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(await apiErrorMessage(res, "Error al cargar solicitudes"));
    const data = await res.json();
    setList(Array.isArray(data) ? data : data.results ?? []);
  };

  const fetchProducts = async () => {
    if (!token) return;
    const res = await fetch("/api/products/productos/", { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const data = await res.json();
    setProducts(Array.isArray(data) ? data : data.results ?? []);
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setError("Inicie sesión para ver solicitudes.");
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([fetchList(), fetchProducts()])
      .catch((err) => setError(err instanceof Error ? err.message : "Error"))
      .finally(() => setLoading(false));
  }, [token, filterEstado]);

  useEffect(() => {
    if (!showDetailModal) setVinculoProductoByDetalle({});
  }, [showDetailModal]);

  const openDetail = async (id: number) => {
    if (!token) return;
    const res = await fetch(`${API_SOLICITUDES}${id}/`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const data: SolicitudFull = await res.json();
    setShowDetailModal(data);
  };

  const changeEstado = async (id: number, estado: Estado, motivoRechazo?: string) => {
    if (!token || !puedeCambiarEstado) return;
    if (estado === "COMPRA_RECHAZADA") {
      const motivo = motivoRechazo ?? window.prompt("Indique el motivo del rechazo (opcional):");
      if (motivo === null) return; // usuario canceló
      motivoRechazo = motivo ?? "";
    }
    setSaving(true);
    try {
      const body: { estado: Estado; motivo_rechazo?: string } = { estado };
      if (estado === "COMPRA_RECHAZADA" && motivoRechazo !== undefined) body.motivo_rechazo = motivoRechazo;
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
      await fetchList();
      setShowDetailModal(null);
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

  const addItem = () => {
    setNewForm((f) => ({ ...f, items: [...f.items, defaultItem()] }));
  };

  const removeItem = (index: number) => {
    setNewForm((f) => ({ ...f, items: f.items.filter((_, i) => i !== index) }));
  };

  const updateItem = (index: number, field: string, value: string | number) => {
    setNewForm((f) => ({
      ...f,
      items: f.items.map((it, i) => (i === index ? { ...it, [field]: value } : it)),
    }));
  };

  const submitNew = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const detalles: Array<{
      producto: number | null;
      descripcion_insumo_solicitado?: string;
      cantidad: number;
      observacion: string;
    }> = [];
    for (const it of newForm.items) {
      if (it.cantidad < 1) continue;
      if (it.tipo === "catalogo") {
        const pid = parseInt(String(it.producto_id), 10);
        if (!Number.isFinite(pid) || pid <= 0) continue;
        detalles.push({ producto: pid, cantidad: it.cantidad, observacion: it.observacion || "" });
      } else {
        const desc = (it.descripcion_fuera || "").trim();
        if (!desc) continue;
        detalles.push({
          producto: null,
          descripcion_insumo_solicitado: desc,
          cantidad: it.cantidad,
          observacion: it.observacion || "",
        });
      }
    }
    if (detalles.length === 0) {
      alert("Agregue al menos un ítem: producto del catálogo o descripción (fuera de catálogo) con cantidad ≥ 1.");
      return;
    }
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
          observacion: newForm.observacion,
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
      await fetchList();
      setShowNewModal(false);
      setNewForm({ destino: "", observacion: "", items: [defaultItem()] });
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando solicitudes...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-gray-800">Solicitudes de compra</h2>
        <div className="flex items-center gap-3">
          {canVerFiltroEstado && (
            <select
              value={filterEstado}
              onChange={(e) => setFilterEstado(e.target.value)}
              className="rounded border-gray-300 text-sm"
            >
              <option value="">Todos los estados</option>
              {Object.entries(ESTADO_LABEL).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          )}
          {canCreateSolicitud && (
            <button
              type="button"
              onClick={() => setShowNewModal(true)}
              className="bg-indigo-600 text-white px-4 py-2 rounded shadow hover:bg-indigo-700 transition"
            >
              Nueva solicitud
            </button>
          )}
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Id</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Destino</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Solicitante</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ítems</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acciones</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {list.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{s.id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{s.fecha}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-800">
                    {ESTADO_LABEL[s.estado]}
                  </span>
                  {s.pendiente_vincular_catalogo && (
                    <span
                      className="ml-1 px-1.5 py-0.5 text-xs rounded bg-amber-100 text-amber-900"
                      title="Hay ítems sin vincular al catálogo"
                    >
                      Catálogo
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{s.destino || "—"}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{s.solicitante_nombre}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{s.cantidad_items}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <button
                    type="button"
                    onClick={() => openDetail(s.id)}
                    className="text-indigo-600 hover:text-indigo-800 mr-2"
                  >
                    Ver
                  </button>
                  {puedeCambiarEstado && (
                    <>
                      {s.estado === "SOLICITADO" && puedePasarARevision && (
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => changeEstado(s.id, "EN_REVISION")}
                          className="text-green-600 hover:text-green-800 disabled:opacity-50"
                        >
                          En revisión
                        </button>
                      )}
                      {s.estado === "EN_REVISION" && (
                        <>
                          {isAdmin && (
                            <>
                              <button
                                type="button"
                                disabled={saving || Boolean(s.pendiente_vincular_catalogo)}
                                title={
                                  s.pendiente_vincular_catalogo
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
                                disabled={saving}
                                onClick={() => changeEstado(s.id, "COMPRA_RECHAZADA")}
                                className="text-red-600 hover:text-red-800 mr-2 disabled:opacity-50"
                              >
                                Rechazar
                              </button>
                            </>
                          )}
                          {!isAdmin && isCompras && (
                            <>
                              {!s.requiere_aprobacion_gerencia && s.stock_cubre_solicitud && (
                                <button
                                  type="button"
                                  disabled={saving || Boolean(s.pendiente_vincular_catalogo)}
                                  onClick={() => changeEstado(s.id, "COMPRA_ACEPTADA")}
                                  className="text-green-600 hover:text-green-800 mr-2 disabled:opacity-50"
                                  title={
                                    s.pendiente_vincular_catalogo
                                      ? "Vincule todas las líneas al catálogo antes de aprobar."
                                      : "Aprobar con stock en depósito (sin circuito Gerencia)"
                                  }
                                >
                                  Aprobar (stock)
                                </button>
                              )}
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
                          {!isAdmin && isGerencia && s.requiere_aprobacion_gerencia && (
                            <>
                              <button
                                type="button"
                                disabled={saving || Boolean(s.pendiente_vincular_catalogo)}
                                onClick={() => changeEstado(s.id, "COMPRA_ACEPTADA")}
                                className="text-green-600 hover:text-green-800 mr-2 disabled:opacity-50"
                                title={
                                  s.pendiente_vincular_catalogo
                                    ? "Vincule todas las líneas al catálogo antes de aprobar."
                                    : "Aprobar con control presupuestario / insumos nuevos o costosos"
                                }
                              >
                                Aprobar (Gerencia)
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
                        </>
                      )}
                      {s.estado === "COMPRA_ACEPTADA" && puedeFinalizar && (
                        <button
                          type="button"
                          disabled={saving}
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
                <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                  No hay solicitudes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal Nueva solicitud */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <h3 className="text-lg font-bold mb-4">Nueva solicitud de compra</h3>
            <form onSubmit={submitNew} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Destino (opcional)</label>
                <input
                  value={newForm.destino}
                  onChange={(e) => setNewForm((f) => ({ ...f, destino: e.target.value }))}
                  className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Observación (opcional)</label>
                <textarea
                  value={newForm.observacion}
                  onChange={(e) => setNewForm((f) => ({ ...f, observacion: e.target.value }))}
                  rows={2}
                  className="mt-1 block w-full rounded border border-gray-300 p-2 text-sm"
                />
              </div>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">Ítems</label>
                  <button type="button" onClick={addItem} className="text-sm text-indigo-600 hover:text-indigo-800">
                    + Agregar ítem
                  </button>
                </div>
                <p className="text-xs text-gray-500 mb-2">
                  Cada línea puede ser del catálogo o fuera de catálogo (solo texto). Compras/Gerencia vincularán lo necesario antes de aprobar.
                </p>
                {newForm.items.map((item, idx) => (
                  <div key={idx} className="mb-3 p-2 border border-gray-200 rounded-md space-y-2">
                    <div className="flex flex-wrap gap-2 items-end">
                      <select
                        value={item.tipo}
                        onChange={(e) =>
                          updateItem(idx, "tipo", e.target.value as ItemRow["tipo"])
                        }
                        className="rounded border border-gray-300 p-2 text-sm"
                      >
                        <option value="catalogo">Catálogo</option>
                        <option value="fuera">Fuera de catálogo</option>
                      </select>
                      {item.tipo === "catalogo" ? (
                        <select
                          value={item.producto_id}
                          onChange={(e) => updateItem(idx, "producto_id", e.target.value)}
                          className="flex-1 min-w-[12rem] rounded border border-gray-300 p-2 text-sm"
                        >
                          <option value="">Seleccionar producto</option>
                          {products.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.sku} - {p.nombre}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          placeholder="Descripción del insumo solicitado"
                          value={item.descripcion_fuera}
                          onChange={(e) => updateItem(idx, "descripcion_fuera", e.target.value)}
                          className="flex-1 min-w-[12rem] rounded border border-gray-300 p-2 text-sm"
                        />
                      )}
                      <input
                        type="number"
                        min={1}
                        value={item.cantidad}
                        onChange={(e) => updateItem(idx, "cantidad", parseInt(e.target.value, 10) || 1)}
                        className="w-20 rounded border border-gray-300 p-2 text-sm"
                        title="Cantidad"
                      />
                      {newForm.items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeItem(idx)}
                          className="text-red-600 hover:text-red-800 p-1"
                          aria-label="Quitar ítem"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <button type="button" onClick={() => setShowNewModal(false)} className="px-4 py-2 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Cancelar
                </button>
                <button type="submit" disabled={saving} className="px-4 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {saving ? "Guardando..." : "Crear solicitud"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Detalle */}
      {showDetailModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
            <h3 className="text-lg font-bold mb-2">Solicitud #{showDetailModal.id}</h3>
            <p className="text-sm text-gray-500 mb-4">
              {showDetailModal.fecha} · {ESTADO_LABEL[showDetailModal.estado]} · {showDetailModal.solicitante_nombre}
            </p>
            {showDetailModal.destino && <p className="text-sm text-gray-700 mb-1">Destino: {showDetailModal.destino}</p>}
            {showDetailModal.observacion && <p className="text-sm text-gray-600 mb-4">{showDetailModal.observacion}</p>}
            {showDetailModal.estado === "COMPRA_RECHAZADA" && showDetailModal.motivo_rechazo && (
              <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2 mb-4">
                <strong>Motivo del rechazo:</strong> {showDetailModal.motivo_rechazo}
              </p>
            )}
            {solicitudPendienteVincular(showDetailModal.detalles) && (
              <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-2 mb-4">
                Hay líneas <strong>fuera de catálogo</strong>. Cree el producto en el catálogo si no existe y vincule cada
                línea antes de poder aprobar la solicitud.
              </p>
            )}
            <table className="min-w-full text-sm mb-4">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Ítem</th>
                  <th className="text-right py-2">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {showDetailModal.detalles.map((d) => (
                  <tr key={d.id} className="border-b border-gray-100 align-top">
                    <td className="py-2">
                      {d.producto != null ? (
                        <span>
                          {d.producto_sku} — {d.producto_nombre}
                        </span>
                      ) : (
                        <span className="text-gray-800">
                          <span className="text-amber-800 font-medium">Fuera de catálogo: </span>
                          {d.descripcion_insumo_solicitado?.trim() || "—"}
                        </span>
                      )}
                      {puedeVincularCatalogo && d.producto == null && (
                        <div className="mt-2 flex flex-wrap gap-2 items-center">
                          <select
                            value={vinculoProductoByDetalle[d.id] ?? ""}
                            onChange={(e) =>
                              setVinculoProductoByDetalle((m) => ({ ...m, [d.id]: e.target.value }))
                            }
                            className="text-xs rounded border border-gray-300 p-1 max-w-[14rem]"
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
                            onClick={() => vincularDetalle(d.id)}
                            className="text-xs px-2 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                          >
                            Vincular
                          </button>
                        </div>
                      )}
                    </td>
                    <td className="text-right py-2 whitespace-nowrap">{d.cantidad}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {showDetailModal.estado === "EN_REVISION" && (
              <p className="text-xs text-gray-600 mb-2">
                {showDetailModal.requiere_aprobacion_gerencia
                  ? "Circuito Gerencia: falta de stock en depósito para surtir la solicitud (líneas ya vinculadas al catálogo)."
                  : "Insumos habituales con stock: puede aprobar Compras."}
              </p>
            )}
            {puedeCambiarEstado && (
              <div className="flex flex-wrap gap-2 pt-2 border-t">
                {showDetailModal.estado === "SOLICITADO" && puedePasarARevision && (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => changeEstado(showDetailModal.id, "EN_REVISION")}
                    className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                  >
                    Pasar a En revisión
                  </button>
                )}
                {showDetailModal.estado === "EN_REVISION" && (
                  <>
                    {isAdmin && (
                      <>
                        <button
                          type="button"
                          disabled={saving || solicitudPendienteVincular(showDetailModal.detalles)}
                          title={
                            solicitudPendienteVincular(showDetailModal.detalles)
                              ? "Vincule todas las líneas al catálogo antes de aprobar."
                              : undefined
                          }
                          onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                        >
                          Aprobar
                        </button>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                          className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                        >
                          Rechazar
                        </button>
                      </>
                    )}
                    {!isAdmin && isCompras && (
                      <>
                        {!showDetailModal.requiere_aprobacion_gerencia &&
                          showDetailModal.stock_cubre_solicitud && (
                            <button
                              type="button"
                              disabled={
                                saving || solicitudPendienteVincular(showDetailModal.detalles)
                              }
                              title={
                                solicitudPendienteVincular(showDetailModal.detalles)
                                  ? "Vincule todas las líneas al catálogo antes de aprobar."
                                  : "Aprobar con stock en depósito (sin circuito Gerencia)"
                              }
                              onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                            >
                              Aprobar (stock)
                            </button>
                          )}
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                          className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                        >
                          Rechazar
                        </button>
                      </>
                    )}
                    {!isAdmin && isGerencia && showDetailModal.requiere_aprobacion_gerencia && (
                      <>
                        <button
                          type="button"
                          disabled={
                            saving || solicitudPendienteVincular(showDetailModal.detalles)
                          }
                          title={
                            solicitudPendienteVincular(showDetailModal.detalles)
                              ? "Vincule todas las líneas al catálogo antes de aprobar."
                              : "Aprobar con control presupuestario / insumos nuevos o costosos"
                          }
                          onClick={() => changeEstado(showDetailModal.id, "COMPRA_ACEPTADA")}
                          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                        >
                          Aprobar (Gerencia)
                        </button>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => changeEstado(showDetailModal.id, "COMPRA_RECHAZADA")}
                          className="px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                        >
                          Rechazar
                        </button>
                      </>
                    )}
                  </>
                )}
                {showDetailModal.estado === "COMPRA_ACEPTADA" && puedeFinalizar && (
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => changeEstado(showDetailModal.id, "FINALIZADO")}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
                  >
                    Finalizar
                  </button>
                )}
              </div>
            )}
            <button
              type="button"
              onClick={() => setShowDetailModal(null)}
              className="mt-4 w-full py-2 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
