import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAccessToken } from "@/contexts/AuthContext";
import { HabitosConsumoSection } from "@/components/HabitosConsumoSection";
import { AnalyticsCorridasSection } from "@/components/AnalyticsCorridasSection";
import { AnalyticsDashboardSection } from "@/components/AnalyticsDashboardSection";
import { apiErrorMessage } from "@/utils/apiFetch";
import { formatIsoDateToDMY } from "@/utils/dateFormat";

const API_DASHBOARD = "/api/dashboard/";

interface DashboardData {
  solicitudes_por_estado: Record<string, number>;
  tiempo_promedio_aprobacion_dias: number;
  top_insumos_solicitados: { producto_sku: string; producto_nombre: string; cantidad_total: number }[];
  productos_stock_critico: number;
  filtro_desde: string;
  filtro_hasta: string;
}

const ESTADO_LABEL: Record<string, string> = {
  SOLICITADO: "Solicitado",
  EN_REVISION: "En revisión",
  COMPRA_ACEPTADA: "Compra aceptada",
  COMPRA_RECHAZADA: "Compra rechazada",
  FINALIZADO: "Finalizado",
};

export function DashboardPage() {
  const token = useAccessToken();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  const fetchDashboard = async () => {
    if (!token) {
      setLoading(false);
      setError("Inicie sesión para ver el dashboard.");
      return;
    }
    const params = new URLSearchParams();
    if (desde) params.set("desde", desde);
    if (hasta) params.set("hasta", hasta);
    const url = params.toString() ? `${API_DASHBOARD}?${params}` : API_DASHBOARD;
    try {
      setError(null);
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) {
        if (res.status === 403) throw new Error("No tiene permiso para ver el dashboard.");
        throw new Error(await apiErrorMessage(res, "Error al cargar el dashboard"));
      }
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchDashboard();
  }, [token, desde, hasta]);

  if (loading) return <div className="text-gray-500">Cargando dashboard...</div>;
  if (error) return <div className="text-red-500">{error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-4">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Desde</label>
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="rounded border border-gray-300 text-sm p-1.5"
          />
          <label className="text-sm text-gray-600 ml-2">Hasta</label>
          <input
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="rounded border border-gray-300 text-sm p-1.5"
          />
        </div>
      </div>

      <p className="text-sm text-gray-500">
        Período: {formatIsoDateToDMY(data.filtro_desde)} — {formatIsoDateToDMY(data.filtro_hasta)}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
          <h3 className="text-sm font-medium text-gray-500 uppercase">Solicitudes por estado</h3>
          <ul className="mt-2 text-sm space-y-1">
            {Object.entries(data.solicitudes_por_estado).map(([estado, cant]) => (
              <li key={estado}>
                {ESTADO_LABEL[estado] || estado}: <strong>{cant}</strong>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
          <h3 className="text-sm font-medium text-gray-500 uppercase">Tiempo promedio aprobación</h3>
          <p className="mt-2 text-2xl font-bold text-gray-800">{data.tiempo_promedio_aprobacion_dias} días</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500">
          <h3 className="text-sm font-medium text-gray-500 uppercase">Productos con stock crítico</h3>
          <p className="mt-2 text-2xl font-bold text-red-700">{data.productos_stock_critico}</p>
          <Link to="/products" className="text-sm text-blue-600 hover:underline mt-1 inline-block">
            Ver productos  →
          </Link>
        </div>
      </div>

      <AnalyticsDashboardSection token={token} desde={desde} hasta={hasta} />

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <h3 className="px-4 py-3 bg-gray-50 text-sm font-medium text-gray-700 uppercase">Top 10 insumos solicitados</h3>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
              <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
              <th className="px-6 py-2 text-center text-xs font-medium text-gray-500 uppercase">Cantidad total</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.top_insumos_solicitados.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-6 py-4 text-center text-sm text-gray-500">
                  No hay datos en el período seleccionado.
                </td>
              </tr>
            ) : (
              data.top_insumos_solicitados.map((item, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-sm text-gray-900">{item.producto_sku}</td>
                  <td className="px-6 py-3 text-sm text-gray-700">{item.producto_nombre}</td>
                  <td className="px-6 py-3 text-sm text-gray-900 font-semibold text-center">{item.cantidad_total}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <HabitosConsumoSection token={token} desde={desde} hasta={hasta} />
      <AnalyticsCorridasSection token={token} />
    </div>
  );
}
