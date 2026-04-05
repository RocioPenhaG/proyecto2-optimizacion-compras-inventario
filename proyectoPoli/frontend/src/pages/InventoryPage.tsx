import { useEffect, useState } from "react";
import { useAccessToken } from "@/contexts/AuthContext";

interface Movement {
  id: number;
  fecha: string;
  tipo: string;
  cantidad: number;
  producto_nombre: string;
  usuario_nombre: string;
  observacion: string;
}

interface Product {
  id: number;
  sku: string;
  nombre: string;
  stock_actual: number;
}

export function InventoryPage() {
  const token = useAccessToken();
  const [movements, setMovements] = useState<Movement[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estados Modal
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    tipo: "IN",
    producto: "",
    cantidad: 1,
    observacion: ""
  });

  const fetchData = async () => {
    if (!token) return;
    try {
      const [resMov, resProd] = await Promise.all([
        fetch("/api/inventory/movimientos/", { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/products/productos/", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      if (!resMov.ok || !resProd.ok) throw new Error("Error al cargar datos");
      
      setMovements(await resMov.json());
      setProducts(await resProd.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
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

      await fetchData();
      setShowModal(false);
      setFormData({ tipo: "IN", producto: "", cantidad: 1, observacion: "" });
    } catch (err) {
      alert("Error: " + (err instanceof Error ? err.message : "No se pudo registrar"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-500">Cargando inventario...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Movimientos de Inventario</h2>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-green-600 text-white px-4 py-2 rounded shadow hover:bg-green-700 transition"
        >
          Registrar Movimiento
        </button>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tipo</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Producto</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cantidad</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Usuario</th>
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
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-bold">
                  {m.tipo === 'OUT' ? '-' : '+'}{m.cantidad}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.usuario_nombre}</td>
              </tr>
            ))}
            {movements.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">No hay movimientos registrados.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal Nuevo Movimiento */}
      {showModal && (
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
                  {products.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.sku} - {p.nombre} (Stock: {p.stock_actual})
                    </option>
                  ))}
                </select>
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