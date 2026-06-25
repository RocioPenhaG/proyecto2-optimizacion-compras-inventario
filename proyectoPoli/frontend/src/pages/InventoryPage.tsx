import { useEffect, useState } from "react";
import { useAccessToken, useAuth } from "@/contexts/AuthContext";

const BUSCAR_DEBOUNCE_MS = 400;

interface Movement {
  id: number;
  fecha: string;
  tipo: string;
  cantidad: number;
  producto_nombre: string;
  usuario_nombre: string;
  observacion: string;
  /** Stock vigente del producto (mismo valor para todas las filas de ese producto). */
  stock_actual?: number;
}

interface Product {
  id: number;
  sku: string;
  nombre: string;
  stock_actual: number;
}

const MOV_PAGE_SIZE = 20;

export function InventoryPage() {
  const token = useAccessToken();
  const { user } = useAuth();
  const canRegistrarMovimiento = ["COMPRAS", "CONTABLE", "ADMINISTRADOR"].includes(user?.role ?? "");
  const canEliminarMovimiento = user?.role === "ADMINISTRADOR";
  const [movements, setMovements] = useState<Movement[]>([]);
  const [movTotal, setMovTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ordenFecha, setOrdenFecha] = useState<"desc" | "asc">("desc");
  const [buscarInput, setBuscarInput] = useState("");
  const [buscarQuery, setBuscarQuery] = useState("");

  // Estados Modal
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    tipo: "IN",
    producto: "",
    cantidad: 1,
    observacion: ""
  });

  const fetchData = async (movementsPage: number) => {
    if (!token) return;
    try {
      setError(null);
      const movParams = new URLSearchParams({
        orden_fecha: ordenFecha,
        page: String(movementsPage),
      });
      if (buscarQuery) {
        movParams.set("buscar", buscarQuery);
      }
      const movsUrl = `/api/inventory/movimientos/?${movParams.toString()}`;
      const [resMov, resProd] = await Promise.all([
        fetch(movsUrl, { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/products/productos/", { headers: { Authorization: `Bearer ${token}` } }),
      ]);

      if (!resMov.ok || !resProd.ok) throw new Error("Error al cargar datos");

      const movJson = await resMov.json();
      if (Array.isArray(movJson)) {
        setMovements(movJson);
        setMovTotal(movJson.length);
      } else {
        setMovements(movJson.results ?? []);
        setMovTotal(typeof movJson.count === "number" ? movJson.count : 0);
      }
      const prodJson = await resProd.json();
      setProducts(Array.isArray(prodJson) ? prodJson : prodJson.results ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    void fetchData(page);
  }, [token, ordenFecha, page, buscarQuery]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      setBuscarQuery((prev) => {
        const next = buscarInput.trim();
        if (prev !== next) {
          setPage(1);
        }
        return next;
      });
    }, BUSCAR_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [buscarInput]);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [page]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !canRegistrarMovimiento) return;

    const productoId = parseInt(formData.producto, 10);
    const productoSel = products.find((p) => p.id === productoId);
    if (formData.tipo === "OUT") {
      const stock = Number(productoSel?.stock_actual ?? 0);
      if (stock <= 0) {
        alert("No hay stock disponible para este producto. Registre una entrada primero.");
        return;
      }
      if (formData.cantidad > stock) {
        alert("El producto seleccionado tiene un stock inferior al solicitado.");
        return;
      }
    }

    setSaving(true);
    
    try {
      const res = await fetch("/api/inventory/movimientos/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({
          ...formData,
          producto: parseInt(formData.producto)
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        // Mostrar mensaje detallado (ej: stock negativo)
        throw new Error(errData[0] || errData.detail || JSON.stringify(errData));
      }

      await fetchData(1);
      setPage(1);
      setShowModal(false);
      setFormData({ tipo: "IN", producto: "", cantidad: 1, observacion: "" });
    } catch (err) {
      alert("Error: " + (err instanceof Error ? err.message : "No se pudo registrar"));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteMovement = async (movId: number) => {
    if (!token || !canEliminarMovimiento) return;
    if (
      !window.confirm(
        "¿Eliminar este movimiento? Se revertirá el efecto en el stock actual del producto.",
      )
    ) {
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`/api/inventory/movimientos/${movId}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err.detail === "string" ? err.detail : "Error al eliminar el movimiento",
        );
      }
      await fetchData(page);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error al eliminar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando inventario...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  const totalPages = Math.max(1, Math.ceil(movTotal / MOV_PAGE_SIZE));
  const fromIdx = movTotal === 0 ? 0 : (page - 1) * MOV_PAGE_SIZE + 1;
  const toIdx = Math.min(page * MOV_PAGE_SIZE, movTotal);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Movimientos de Inventario</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="orden-fecha" className="text-sm text-gray-600">
              Ordenar por:
            </label>
            <select
              id="orden-fecha"
              value={ordenFecha}
              onChange={(e) => {
                setOrdenFecha(e.target.value as "asc" | "desc");
                setPage(1);
              }}
              className="rounded border border-gray-300 text-sm p-2 bg-white"
            >
              <option value="desc">Más recientes primero</option>
              <option value="asc">Más antiguos primero</option>
            </select>
          </div>
          {canRegistrarMovimiento && (
            <button
              onClick={() => setShowModal(true)}
              className="bg-green-600 text-white px-4 py-2 rounded shadow hover:bg-green-700 transition"
            >
              Registrar Movimiento
            </button>
          )}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
        <label htmlFor="buscar-producto-mov" className="block text-sm font-medium text-gray-700 mb-1">
          Buscar por producto
        </label>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          <input
            id="buscar-producto-mov"
            type="search"
            value={buscarInput}
            onChange={(e) => setBuscarInput(e.target.value)}
            placeholder="Nombre o SKU, ej. Pilas AA"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-1 focus:ring-green-500"
            autoComplete="off"
          />
          {buscarInput.trim() !== "" && (
            <button
              type="button"
              onClick={() => {
                setBuscarInput("");
                setBuscarQuery("");
                setPage(1);
              }}
              className="shrink-0 px-3 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Limpiar
            </button>
          )}
        </div>
        <p className="mt-1.5 text-xs text-gray-500">
          Se muestran solo movimientos cuyo producto coincide con el texto (nombre o código).
        </p>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tipo</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Producto</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                <span className="block">Cantidad</span>
                <span className="block font-normal normal-case text-gray-400">Stock actual</span>
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Usuario</th>
              {canEliminarMovimiento && (
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              )}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {movements.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(m.fecha).toLocaleString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    m.tipo === 'IN' ? 'bg-green-100 text-green-800' :
                    m.tipo === 'OUT' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {m.tipo === 'IN' ? 'Entrada' : m.tipo === 'OUT' ? 'Salida' : 'Ajuste'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{m.producto_nombre}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm align-top">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-gray-900 font-bold tabular-nums">
                      {m.tipo === "OUT" ? "-" : "+"}
                      {m.cantidad}
                    </span>
                    <span className="text-gray-500 font-normal text-xs tabular-nums">
                      · stock{" "}
                      {typeof m.stock_actual === "number" ? m.stock_actual : "—"}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.usuario_nombre}</td>
                {canEliminarMovimiento && (
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => handleDeleteMovement(m.id)}
                      className="text-red-700 hover:text-red-900 font-medium disabled:opacity-50"
                    >
                      Eliminar
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {movements.length === 0 && (
              <tr>
                <td colSpan={canEliminarMovimiento ? 6 : 5} className="px-6 py-4 text-center text-sm text-gray-500">
                  {buscarQuery
                    ? `No hay movimientos que coincidan con «${buscarQuery}».`
                    : "No hay movimientos registrados."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p className="text-sm text-gray-600">
            {movTotal === 0
              ? "Sin movimientos"
              : `Mostrando ${fromIdx}–${toIdx} de ${movTotal} movimientos`}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 text-sm font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Anterior
            </button>
            <span className="text-sm text-gray-600 tabular-nums">
              Página {page} de {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="px-3 py-1.5 text-sm font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>

      {/* Modal Nuevo Movimiento */}
      {showModal && canRegistrarMovimiento && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold mb-4">Registrar Movimiento de Stock</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Tipo de movimiento</label>
                  <select 
                    value={formData.tipo} 
                    onChange={e => setFormData({...formData, tipo: e.target.value})} 
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm border p-2 bg-white"
                  >
                    <option value="IN">Entrada (Sumar)</option>
                    <option value="OUT">Salida (Restar)</option>
                    <option value="ADJ">Ajuste (Sumar/Restar)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Cantidad*</label>
                  <input 
                    type="number" 
                    required 
                    min="1" 
                    value={formData.cantidad} 
                    onChange={e => setFormData({...formData, cantidad: parseInt(e.target.value) || 1})} 
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm border p-2" 
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Producto*</label>
                <select 
                  required
                  value={formData.producto} 
                  onChange={e => setFormData({...formData, producto: e.target.value})} 
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm border p-2 bg-white"
                >
                  <option value="">-- Seleccionar producto --</option>
                  {products.map(p => {
                    const stock = Number(p.stock_actual ?? 0);
                    const sinStock = formData.tipo === "OUT" && stock <= 0;
                    return (
                      <option key={p.id} value={p.id} disabled={sinStock}>
                        {p.sku} - {p.nombre} (Stock: {stock})
                        {sinStock ? " — sin stock" : ""}
                      </option>
                    );
                  })}
                </select>
                {formData.tipo === "OUT" && (
                  <p className="mt-1 text-xs text-gray-500">
                    Solo puede registrar salidas de productos con stock disponible.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Observación</label>
                <textarea 
                  rows={2}
                  value={formData.observacion} 
                  onChange={e => setFormData({...formData, observacion: e.target.value})} 
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm border p-2"
                  placeholder="Motivo del movimiento, ej. 'Recepción de compra'"
                />
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Cancelar
                </button>
                <button type="submit" disabled={saving} className="px-4 py-2 bg-green-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-green-700 disabled:bg-green-400">
                  {saving ? "Registrando..." : "Registrar Movimiento"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}