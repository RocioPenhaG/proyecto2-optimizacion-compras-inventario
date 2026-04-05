import { useEffect, useState } from "react";
import { useAccessToken, useAuth } from "@/contexts/AuthContext";

interface Product {
  id: number;
  sku: string;
  nombre: string;
  unidad: string;
  categoria: string;
  stock_actual?: number;
  stock_minimo?: number;
  proveedor_nombre: string | null;
}

interface Proveedor {
  id: number;
  nombre: string;
}

export function ProductsPage() {
  const token = useAccessToken();
  const { user } = useAuth();
  const isFuncionario = user?.role === "FUNCIONARIO";
  const [products, setProducts] = useState<Product[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estados para el Modal
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    sku: "",
    nombre: "",
    unidad: "UNIDAD",
    categoria: "",
    stock_minimo: 0,
    proveedor: ""
  });

  const fetchData = async () => {
    if (!token) return;
    try {
      const resProd = await fetch("/api/products/productos/", {
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
    fetchData();
  }, [token, isFuncionario]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || isFuncionario) return;
    setSaving(true);
    
    try {
      const payload = {
        ...formData,
        proveedor: formData.proveedor ? parseInt(formData.proveedor) : null
      };

      const res = await fetch("/api/products/productos/", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(JSON.stringify(errData));
      }

      // Recargar lista y cerrar modal
      await fetchData();
      setShowModal(false);
      setFormData({ sku: "", nombre: "", unidad: "UNIDAD", categoria: "", stock_minimo: 0, proveedor: "" });
    } catch (err) {
      alert("Error al guardar: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando productos...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Catálogo de Productos</h2>
        {!isFuncionario && (
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 transition"
          >
            Nuevo Producto
          </button>
        )}
      </div>
      
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SKU</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nombre</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Categoría</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Proveedor</th>
              {!isFuncionario && (
                <>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Stock Actual
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Estado stock
                  </th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {products.map((p) => {
              const stockMin = p.stock_minimo ?? 0;
              const stockAct = p.stock_actual ?? 0;
              const esCritico = !isFuncionario && stockMin > 0 && stockAct < stockMin;
              return (
                <tr key={p.id} className={esCritico ? "hover:bg-red-50 bg-red-50/50" : "hover:bg-gray-50"}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{p.sku}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{p.nombre}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{p.categoria || "-"}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{p.proveedor_nombre || "Sin proveedor"}</td>
                  {!isFuncionario && (
                    <>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-semibold">
                        {stockAct} {p.unidad}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {esCritico ? (
                          <span
                            className="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-800"
                            title={`Mínimo: ${stockMin}`}
                          >
                            Crítico
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-700">
                            OK
                          </span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
            {products.length === 0 && (
              <tr>
                <td
                  colSpan={isFuncionario ? 4 : 6}
                  className="px-6 py-4 text-center text-sm text-gray-500"
                >
                  No hay productos registrados.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal Nuevo Producto */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold mb-4">Crear Nuevo Producto</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">SKU (Código)*</label>
                  <input required value={formData.sku} onChange={e => setFormData({...formData, sku: e.target.value})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2" />
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
                <div>
                  <label className="block text-sm font-medium text-gray-700">Stock Mínimo</label>
                  <input type="number" min="0" value={formData.stock_minimo} onChange={e => setFormData({...formData, stock_minimo: parseInt(e.target.value) || 0})} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm border p-2" />
                </div>
              </div>

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
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">
                  Cancelar
                </button>
                <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400">
                  {saving ? "Guardando..." : "Guardar Producto"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}