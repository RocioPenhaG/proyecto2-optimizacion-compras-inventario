import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAccessToken, useAuth } from "@/contexts/AuthContext";

interface Product {
  id: number;
  sku: string;
  nombre: string;
  unidad: string;
  categoria: string;
  stock_actual?: number;
  stock_minimo?: number;
  proveedor?: number | null;
  proveedor_nombre: string | null;
}

interface Proveedor {
  id: number;
  nombre: string;
}

type OrdenProductos = "creacion_asc" | "creacion_desc";

const BUSCAR_DEBOUNCE_MS = 400;

export function ProductsPage() {
  const token = useAccessToken();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const openedFromSolicitudRef = useRef(false);
  const isFuncionario = user?.role === "FUNCIONARIO";
  const canManageProductos = ["COMPRAS", "CONTABLE", "ADMINISTRADOR"].includes(user?.role ?? "");
  const canDeleteProductos = user?.role === "ADMINISTRADOR";
  const showStockColumns = !isFuncionario;
  const tableMinWidth = isFuncionario
    ? "min-w-[36rem]"
    : canManageProductos
      ? "min-w-[52rem]"
      : "min-w-[48rem]";
  const tableColSpan = isFuncionario ? 4 : canManageProductos ? 7 : 6;
  const accionesStickyClass =
    "sticky right-0 z-10 min-w-[9.5rem] whitespace-nowrap shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.12)]";
  const vinculoSolicitudId = searchParams.get("solicitud");
  const vinculoDetalleId = searchParams.get("detalle");
  const destinoCompraParam = searchParams.get("destino_compra");
  const [destinoCompraSolicitud, setDestinoCompraSolicitud] = useState<
    "INVENTARIO" | "ENTREGA_INMEDIATA" | null
  >(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [buscarInput, setBuscarInput] = useState("");
  const [buscarQuery, setBuscarQuery] = useState("");
  const [orden, setOrden] = useState<OrdenProductos>("creacion_asc");

  // Estados para el Modal (crear o editar)
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  /** True solo al abrir el formulario desde «Ir a productos» en una solicitud. */
  const [creacionRapidaSolicitud, setCreacionRapidaSolicitud] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    sku: "",
    nombre: "",
    unidad: "UNIDAD",
    categoria: "",
    stock_minimo: 0,
    stock_inicial: 1,
    proveedor: ""
  });

  const mostrarStockInicial = creacionRapidaSolicitud && editingId == null;
  const esEntregaInmediataSolicitud =
    destinoCompraSolicitud === "ENTREGA_INMEDIATA" || destinoCompraParam === "ENTREGA_INMEDIATA";
  const esInventarioSolicitud =
    destinoCompraSolicitud === "INVENTARIO" || destinoCompraParam === "INVENTARIO";

  const fetchData = async () => {
    if (!token) return;
    try {
      const params = new URLSearchParams({ orden });
      if (buscarQuery) params.set("buscar", buscarQuery);
      const resProd = await fetch(`/api/products/productos/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resProd.ok) throw new Error("Error al cargar datos");
      const raw = await resProd.json();
      setProducts(Array.isArray(raw) ? raw : raw.results ?? []);

      if (!isFuncionario) {
        const resProv = await fetch("/api/products/proveedores/", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!resProv.ok) throw new Error("Error al cargar datos");
        const provRaw = await resProv.json();
        setProveedores(Array.isArray(provRaw) ? provRaw : provRaw.results ?? []);
      } else {
        setProveedores([]);
      }
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
    setLoading(true);
    void fetchData();
  }, [token, isFuncionario, buscarQuery, orden]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      setBuscarQuery(buscarInput.trim());
    }, BUSCAR_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [buscarInput]);

  useEffect(() => {
    if (!token || !vinculoSolicitudId || !canManageProductos) return;
    const id = parseInt(vinculoSolicitudId, 10);
    if (!Number.isFinite(id) || id <= 0) return;
    void fetch(`/api/purchases/solicitudes/${id}/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { tipo_destino_compra?: "INVENTARIO" | "ENTREGA_INMEDIATA" } | null) => {
        if (data?.tipo_destino_compra) setDestinoCompraSolicitud(data.tipo_destino_compra);
      })
      .catch(() => undefined);
  }, [token, vinculoSolicitudId, canManageProductos]);

  useEffect(() => {
    if (loading || !canManageProductos || openedFromSolicitudRef.current) return;
    if (searchParams.get("crear") !== "1") return;
    if (vinculoSolicitudId && !destinoCompraSolicitud && !destinoCompraParam) return;

    openedFromSolicitudRef.current = true;
    const nombreSugerido = (searchParams.get("nombre") ?? "").trim();
    const cantidadSugerida = parseInt(searchParams.get("cantidad") ?? "", 10);
    const cantidadInicial =
      Number.isFinite(cantidadSugerida) && cantidadSugerida > 0 ? cantidadSugerida : 1;
    const esInventario =
      destinoCompraSolicitud === "INVENTARIO" || destinoCompraParam === "INVENTARIO";
    setEditingId(null);
    setCreacionRapidaSolicitud(true);
    setFormData({
      sku: "",
      nombre: nombreSugerido,
      unidad: "UNIDAD",
      categoria: "",
      stock_minimo: esInventario ? cantidadInicial : 0,
      stock_inicial: cantidadInicial,
      proveedor: "",
    });
    setShowModal(true);

    const next = new URLSearchParams(searchParams);
    next.delete("crear");
    next.delete("nombre");
    next.delete("cantidad");
    setSearchParams(next, { replace: true });
  }, [
    loading,
    canManageProductos,
    searchParams,
    setSearchParams,
    vinculoSolicitudId,
    destinoCompraSolicitud,
    destinoCompraParam,
  ]);

  const emptyForm = () =>
    setFormData({
      sku: "",
      nombre: "",
      unidad: "UNIDAD",
      categoria: "",
      stock_minimo: 0,
      stock_inicial: 1,
      proveedor: "",
    });

  const openCreateModal = () => {
    setEditingId(null);
    setCreacionRapidaSolicitud(false);
    emptyForm();
    setShowModal(true);
  };

  const openEditModal = (p: Product) => {
    setCreacionRapidaSolicitud(false);
    setEditingId(p.id);
    setFormData({
      sku: p.sku ?? "",
      nombre: p.nombre,
      unidad: p.unidad || "UNIDAD",
      categoria: p.categoria ?? "",
      stock_minimo: Number(p.stock_minimo ?? 0),
      stock_inicial: 1,
      proveedor: p.proveedor != null ? String(p.proveedor) : "",
    });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingId(null);
    setCreacionRapidaSolicitud(false);
    emptyForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !canManageProductos) return;

    if (mostrarStockInicial && formData.stock_inicial < 1) {
      alert("Indique las unidades compradas (stock actual) para el nuevo producto.");
      return;
    }
    if (mostrarStockInicial && esInventarioSolicitud && formData.stock_minimo < 1) {
      alert("Indique el stock mínimo para activar el control de inventario.");
      return;
    }

    const esCreacionRapida = mostrarStockInicial;
    setSaving(true);

    try {
      const skuTrim = formData.sku.trim();
      const payload: Record<string, string | number | null> = {
        nombre: formData.nombre,
        unidad: formData.unidad,
        categoria: formData.categoria,
        stock_minimo: esCreacionRapida && esEntregaInmediataSolicitud ? 0 : formData.stock_minimo,
        proveedor: formData.proveedor ? parseInt(formData.proveedor, 10) : null,
      };
      if (skuTrim) payload.sku = skuTrim;

      const url =
        editingId != null
          ? `/api/products/productos/${editingId}/`
          : "/api/products/productos/";
      const method = editingId != null ? "PATCH" : "POST";

      if (esCreacionRapida && vinculoSolicitudId) {
        payload.stock_inicial = formData.stock_inicial;
        payload.solicitud_id = parseInt(vinculoSolicitudId, 10);
      }

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(JSON.stringify(errData));
      }

      const saved = (await res.json()) as { id: number };
      await fetchData();
      closeModal();

      if (esCreacionRapida && vinculoSolicitudId) {
        const returnParams = new URLSearchParams({ solicitud: vinculoSolicitudId });
        if (vinculoDetalleId) returnParams.set("detalle", vinculoDetalleId);
        returnParams.set("producto", String(saved.id));
        navigate(`/solicitudes?${returnParams.toString()}`);
        return;
      }
    } catch (err) {
      alert("Error al guardar: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteProduct = async (productId: number, nombre: string) => {
    if (!token || !canDeleteProductos) return;
    if (
      !window.confirm(
        `¿Eliminar el producto «${nombre}»? Se desvinculará de solicitudes y se borrarán movimientos y stock asociados.`,
      )
    ) {
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`/api/products/productos/${productId}/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err.detail === "string" ? err.detail : "Error al eliminar el producto",
        );
      }
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error al eliminar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando productos...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  const volverASolicitudUrl =
    vinculoSolicitudId != null
      ? `/solicitudes?solicitud=${encodeURIComponent(vinculoSolicitudId)}${
          vinculoDetalleId ? `&detalle=${encodeURIComponent(vinculoDetalleId)}` : ""
        }`
      : null;

  return (
    <div className="space-y-6 min-w-0">
      {vinculoSolicitudId && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          Vinculación con la solicitud <strong>#{vinculoSolicitudId}</strong>.
          {volverASolicitudUrl && (
            <>
              {" "}
              <Link to={volverASolicitudUrl} className="font-medium text-blue-700 hover:text-blue-900 underline">
                Volver a la solicitud
              </Link>
            </>
          )}
          {!creacionRapidaSolicitud && (
            <span className="block mt-1 text-xs text-amber-900">
              Si crea el producto desde este menú, cargue las unidades en{" "}
              <Link to="/inventory" className="underline font-medium">
                Inventario
              </Link>{" "}
              (entrada de stock).
            </span>
          )}
        </div>
      )}
      <div className="flex flex-wrap justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-gray-800">Catálogo de Productos</h2>
        {canManageProductos && (
          <button
            type="button"
            onClick={openCreateModal}
            className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 transition"
          >
            Nuevo Producto
          </button>
        )}
      </div>

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3 sm:items-end">
        <div className="flex-1 min-w-[12rem]">
          <label htmlFor="buscar-producto" className="block text-sm font-medium text-gray-700 mb-1">
            Buscar producto
          </label>
          <input
            id="buscar-producto"
            type="search"
            value={buscarInput}
            onChange={(e) => setBuscarInput(e.target.value)}
            placeholder="SKU, nombre o categoría…"
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="min-w-[14rem]">
          <label htmlFor="orden-producto" className="block text-sm font-medium text-gray-700 mb-1">
            Ordenar por
          </label>
          <select
            id="orden-producto"
            value={orden}
            onChange={(e) => setOrden(e.target.value as OrdenProductos)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          >
            <option value="creacion_asc">Creación (más antiguos primero)</option>
            <option value="creacion_desc">Creación (más recientes primero)</option>
          </select>
        </div>
      </div>
      
      <div className="bg-white shadow sm:rounded-lg">
        <div className="overflow-x-auto">
          <table className={`w-full ${tableMinWidth} divide-y divide-gray-200`} data-testid="tabla-inventario">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                  SKU
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[10rem]">
                  Nombre
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                  Categoría
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[8rem]">
                  Proveedor
                </th>
                {showStockColumns && (
                  <>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Stock (actual / mín.)
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Estado stock
                    </th>
                    {canManageProductos && (
                      <th
                        className={`px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50 ${accionesStickyClass}`}
                      >
                        Acciones
                      </th>
                    )}
                  </>
                )}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {products.map((p) => {
                const stockMin = Number(p.stock_minimo ?? 0);
                const stockAct = Number(p.stock_actual ?? 0);
                const esCritico = showStockColumns && stockMin > 0 && stockAct <= stockMin;
                const filaBg = esCritico ? "bg-red-50/50" : "bg-white";
                return (
                  <tr key={p.id} className={esCritico ? "hover:bg-red-50 bg-red-50/50" : "hover:bg-gray-50"}>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{p.sku}</td>
                    <td
                      className="px-4 py-4 text-sm font-medium text-gray-900 max-w-[14rem] truncate"
                      title={p.nombre}
                    >
                      {p.nombre}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">{p.categoria || "-"}</td>
                    <td
                      className="px-4 py-4 text-sm text-gray-500 max-w-[12rem] truncate"
                      title={p.proveedor_nombre ?? undefined}
                    >
                      {p.proveedor_nombre || "Sin proveedor"}
                    </td>
                    {showStockColumns && (
                      <>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900" data-testid={`stock-producto-${p.id}`}>
                          <span className="font-semibold">
                            {stockAct} {p.unidad}
                          </span>
                          <span className="text-gray-500 font-normal ml-2">
                            mín. {stockMin} {p.unidad}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          {esCritico ? (
                            <span
                              className="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-800"
                              data-testid="alerta-stock-critico"
                            >
                              Crítico
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-700">
                              OK
                            </span>
                          )}
                        </td>
                        {canManageProductos && (
                          <td className={`px-4 py-4 text-right text-sm ${filaBg} ${accionesStickyClass}`}>
                            <div className="inline-flex flex-wrap items-center justify-end gap-2 whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => openEditModal(p)}
                                className="text-blue-600 hover:text-blue-800 font-medium shrink-0"
                              >
                                Editar
                              </button>
                              {canDeleteProductos && (
                                <button
                                  type="button"
                                  disabled={saving}
                                  onClick={() => handleDeleteProduct(p.id, p.nombre)}
                                  className="text-red-700 hover:text-red-900 font-medium disabled:opacity-50 shrink-0"
                                >
                                  Eliminar
                                </button>
                              )}
                            </div>
                          </td>
                        )}
                      </>
                    )}
                  </tr>
                );
              })}
              {products.length === 0 && (
                <tr>
                  <td colSpan={tableColSpan} className="px-4 py-4 text-center text-sm text-gray-500">
                    {buscarQuery
                      ? `No hay productos que coincidan con «${buscarQuery}».`
                      : "No hay productos registrados."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Nuevo Producto */}
      {showModal && canManageProductos && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold mb-4">
              {editingId != null
                ? "Editar producto"
                : mostrarStockInicial
                  ? "Crear producto para la solicitud"
                  : "Crear Nuevo Producto"}
            </h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">SKU (opcional)</label>
                  <input
                    value={formData.sku}
                    onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                    placeholder="Vacío = SPK-0001, SPK-0002…"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
                  />
                  {editingId == null ? (
                    <p className="mt-1 text-xs text-gray-500">
                      Si lo deja vacío, el sistema asigna un código automático.
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-gray-500">
                      Deje el SKU vacío para conservar el actual.
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Categoría</label>
                  <input value={formData.categoria} onChange={e => setFormData({...formData, categoria: e.target.value})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2" />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">Nombre del Producto*</label>
                <input required value={formData.nombre} onChange={e => setFormData({...formData, nombre: e.target.value})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Unidad de medida</label>
                  <input value={formData.unidad} onChange={e => setFormData({...formData, unidad: e.target.value})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2" placeholder="ej. UNIDAD, KG, LITROS" />
                </div>
                {!(mostrarStockInicial && esEntregaInmediataSolicitud) && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Stock Mínimo{mostrarStockInicial && esInventarioSolicitud ? "*" : ""}
                    </label>
                    <input
                      type="number"
                      min={mostrarStockInicial && esInventarioSolicitud ? 1 : 0}
                      required={mostrarStockInicial && esInventarioSolicitud}
                      value={formData.stock_minimo}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          stock_minimo: parseInt(e.target.value, 10) || 0,
                        })
                      }
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
                    />
                    {mostrarStockInicial && esInventarioSolicitud && (
                      <p className="mt-1 text-xs text-gray-500">
                        Se usará para alertas de stock crítico en el dashboard.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {mostrarStockInicial && esEntregaInmediataSolicitud && (
                <p className="text-xs text-violet-800 bg-violet-50 border border-violet-200 rounded-md p-3">
                  Entrega inmediata: no se configura stock mínimo ni alertas por stock en cero.
                </p>
              )}

              {mostrarStockInicial && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Stock actual (unidades compradas)*
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.stock_inicial}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        stock_inicial: Math.max(1, parseInt(e.target.value, 10) || 1),
                      })
                    }
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Se registrará una entrada de inventario con esta cantidad al crear el producto.
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700">Proveedor</label>
                <select value={formData.proveedor} onChange={e => setFormData({...formData, proveedor: e.target.value})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2 bg-white">
                  <option value="">-- Sin proveedor --</option>
                  {proveedores.map(prov => (
                    <option key={prov.id} value={prov.id}>{prov.nombre}</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400"
                >
                  {saving ? "Guardando..." : editingId != null ? "Guardar cambios" : "Guardar Producto"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}