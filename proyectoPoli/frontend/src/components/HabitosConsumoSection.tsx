/**
 * Sección "Hábitos de consumo" del dashboard (Release 2).
 * Consume /api/analytics/habitos-resumen/ y muestra gráficos y tablas.
 */
import { useEffect, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  BarController,
} from "chart.js";
import { Bar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  BarController,
);

const API_HABITOS = "/api/analytics/habitos-resumen/";
const DIAS_SEMANA = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

interface ConsumoMensualItem {
  producto_id: number;
  producto_sku: string;
  producto_nombre: string;
  anio: number;
  mes: number;
  cantidad_total: number;
  promedio_diario: number;
}

interface ConsumoPorDiaItem {
  producto_id: number;
  producto_sku: string;
  producto_nombre: string;
  dia_semana: number;
  cantidad_total: number;
}

interface HabitosData {
  consumo_mensual: ConsumoMensualItem[];
  consumo_por_dia_semana: ConsumoPorDiaItem[];
  filtro_desde: string;
  filtro_hasta: string;
}

interface HabitosConsumoSectionProps {
  token: string | null;
  desde: string;
  hasta: string;
}

export function HabitosConsumoSection({ token, desde, hasta }: HabitosConsumoSectionProps) {
  const [data, setData] = useState<HabitosData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const params = new URLSearchParams();
    if (desde) params.set("desde", desde);
    if (hasta) params.set("hasta", hasta);
    const url = params.toString() ? `${API_HABITOS}?${params}` : API_HABITOS;
    setLoading(true);
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (res.status === 403) throw new Error("No tiene permiso para ver hábitos de consumo.");
        if (!res.ok) throw new Error("Error al cargar hábitos");
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [token, desde, hasta]);

  if (loading) return <p className="text-sm text-gray-500">Cargando hábitos de consumo...</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!data) return null;

  const { consumo_mensual, consumo_por_dia_semana } = data;

  // Agrupar consumo mensual por (anio-mes) para el gráfico de barras (suma de todos los productos o por producto)
  const labelsMensual = Array.from(
    new Set(consumo_mensual.map((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}`))
  ).sort();
  const porMes = labelsMensual.map((label) => {
    const total = consumo_mensual
      .filter((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}` === label)
      .reduce((s, r) => s + r.cantidad_total, 0);
    return total;
  });

  const chartMensual = {
    labels: labelsMensual,
    datasets: [
      {
        label: "Consumo total (salidas)",
        data: porMes,
        backgroundColor: "rgba(59, 130, 246, 0.6)",
        borderColor: "rgb(59, 130, 246)",
        borderWidth: 1,
      },
    ],
  };

  const optsMensual = {
    responsive: true,
    plugins: {
      legend: { position: "top" as const },
      title: { display: true, text: "Consumo mensual (total por mes)" },
    },
    scales: {
      y: { beginAtZero: true },
    },
  };

  // Por día de semana: agregar por dia_semana (1=Dom en Django ExtractWeekDay)
  const porDiaSemana = [1, 2, 3, 4, 5, 6, 7].map((d) => {
    const total = consumo_por_dia_semana
      .filter((r) => r.dia_semana === d)
      .reduce((s, r) => s + r.cantidad_total, 0);
    return total;
  });

  const chartDiaSemana = {
    labels: DIAS_SEMANA,
    datasets: [
      {
        label: "Consumo por día de la semana",
        data: porDiaSemana,
        backgroundColor: "rgba(34, 197, 94, 0.6)",
        borderColor: "rgb(34, 197, 94)",
        borderWidth: 1,
      },
    ],
  };

  const optsDiaSemana = {
    responsive: true,
    plugins: {
      legend: { position: "top" as const },
      title: { display: true, text: "Consumo por día de la semana" },
    },
    scales: {
      y: { beginAtZero: true },
    },
  };

  // Tabla: consumo mensual por producto (agrupar por producto, mostrar filas producto + meses)
  const productosUnicos = Array.from(
    new Map(consumo_mensual.map((r) => [r.producto_id, { sku: r.producto_sku, nombre: r.producto_nombre }])).entries()
  );
  const tablaPorProducto = productosUnicos.map(([id, info]) => {
    const filas = consumo_mensual.filter((r) => r.producto_id === id);
    const total = filas.reduce((s, r) => s + r.cantidad_total, 0);
    const promedio = filas.length ? total / filas.length : 0;
    return { producto_id: id, sku: info.sku, nombre: info.nombre, total, promedio, meses: filas.length };
  }).sort((a, b) => b.total - a.total);

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Hábitos de consumo</h3>
      <p className="text-sm text-gray-500">
        Período: {data.filtro_desde} — {data.filtro_hasta}
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <Bar data={chartMensual} options={optsMensual} />
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <Bar data={chartDiaSemana} options={optsDiaSemana} />
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <h4 className="px-4 py-3 bg-gray-50 text-sm font-medium text-gray-700 uppercase">
          Consumo por producto (resumen en el período)
        </h4>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
              <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
              <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total período</th>
              <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Promedio/mes</th>
              <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Meses con datos</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tablaPorProducto.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                  No hay datos de consumo en el período.
                </td>
              </tr>
            ) : (
              tablaPorProducto.map((row) => (
                <tr key={row.producto_id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-sm text-gray-900">{row.sku}</td>
                  <td className="px-6 py-3 text-sm text-gray-700">{row.nombre}</td>
                  <td className="px-6 py-3 text-sm text-right font-medium">{row.total}</td>
                  <td className="px-6 py-3 text-sm text-right">{row.promedio.toFixed(1)}</td>
                  <td className="px-6 py-3 text-sm text-right">{row.meses}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {consumo_mensual.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <h4 className="px-4 py-3 bg-gray-50 text-sm font-medium text-gray-700 uppercase">
            Detalle consumo mensual por producto
          </h4>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Año-Mes</th>
                <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Cantidad</th>
                <th className="px-6 py-2 text-right text-xs font-medium text-gray-500 uppercase">Promedio diario</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {consumo_mensual.slice(0, 50).map((r, idx) => (
                <tr key={`${r.producto_id}-${r.anio}-${r.mes}-${idx}`} className="hover:bg-gray-50">
                  <td className="px-6 py-2 text-sm text-gray-900">{r.producto_sku}</td>
                  <td className="px-6 py-2 text-sm text-gray-700">{r.anio}-{String(r.mes).padStart(2, "0")}</td>
                  <td className="px-6 py-2 text-sm text-right">{r.cantidad_total}</td>
                  <td className="px-6 py-2 text-sm text-right">{r.promedio_diario.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {consumo_mensual.length > 50 && (
            <p className="px-4 py-2 text-sm text-gray-500">Mostrando los primeros 50 registros.</p>
          )}
        </div>
      )}
    </div>
  );
}
