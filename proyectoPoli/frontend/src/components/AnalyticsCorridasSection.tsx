import { useEffect, useMemo, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  LineController,
} from "chart.js";
import { Line } from "react-chartjs-2";
import {
  getAnalyticsCorridas,
  getAnalyticsCorridaStatus,
  getAnalyticsCorridaTendencias,
  getAnalyticsTendenciaVisual,
  type CorridaAnalytics,
  type EstadoCorridaResponse,
  type TendenciaLinealItem,
  type TendenciaVisualResponse,
} from "@/services/api";

interface AnalyticsCorridasSectionProps {
  token: string | null;
}

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  LineController,
);

function tendenciaLabel(pendiente: number | undefined) {
  if (pendiente == null) return "N/D";
  if (pendiente > 0) return "Creciente";
  if (pendiente < 0) return "Decreciente";
  return "Estable";
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function fmt(value: unknown, digits = 2): string {
  const n = asNumber(value);
  return n == null ? "N/D" : n.toFixed(digits);
}

function fmtSigned(value: unknown, digits = 0): string {
  const n = asNumber(value);
  if (n == null) return "N/D";
  if (n > 0) return `+${n.toFixed(digits)}`;
  if (n < 0) return n.toFixed(digits);
  return n.toFixed(digits);
}

function fmtDate(value: unknown): string {
  if (typeof value !== "string" || value.trim() === "") return "N/D";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

export function AnalyticsCorridasSection({ token }: AnalyticsCorridasSectionProps) {
  const [corridas, setCorridas] = useState<CorridaAnalytics[]>([]);
  const [selectedCorridaId, setSelectedCorridaId] = useState<number | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<EstadoCorridaResponse | null>(null);
  const [tendencias, setTendencias] = useState<TendenciaLinealItem[]>([]);
  const [selectedTendenciaId, setSelectedTendenciaId] = useState<number | null>(null);
  const [tendenciaVisual, setTendenciaVisual] = useState<TendenciaVisualResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(false);
  const [tendenciasLoading, setTendenciasLoading] = useState(false);
  const [tendenciaVisualLoading, setTendenciaVisualLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    getAnalyticsCorridas(token, 10)
      .then((res) => {
        setCorridas(res.results || []);
        const firstCorrida = (res.results || [])[0];
        const firstTaskId = (res.results || []).find((c) => c.task_id)?.task_id ?? null;
        setSelectedCorridaId(firstCorrida?.id ?? null);
        setSelectedTaskId(firstTaskId);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar corridas"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token || !selectedTaskId) {
      setStatusData(null);
      return;
    }
    setStatusLoading(true);
    getAnalyticsCorridaStatus(token, selectedTaskId)
      .then(setStatusData)
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar estado"))
      .finally(() => setStatusLoading(false));
  }, [token, selectedTaskId]);

  useEffect(() => {
    if (!token || selectedCorridaId == null) {
      setTendencias([]);
      setSelectedTendenciaId(null);
      setTendenciaVisual(null);
      return;
    }
    setTendenciasLoading(true);
    getAnalyticsCorridaTendencias(token, selectedCorridaId)
      .then((res) => {
        const nextTendencias = res.results || [];
        setTendencias(nextTendencias);
        setSelectedTendenciaId(nextTendencias[0]?.id ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar tendencias"))
      .finally(() => setTendenciasLoading(false));
  }, [token, selectedCorridaId]);

  useEffect(() => {
    if (!token || selectedTendenciaId == null) {
      setTendenciaVisual(null);
      return;
    }
    setTendenciaVisualLoading(true);
    getAnalyticsTendenciaVisual(token, selectedTendenciaId)
      .then(setTendenciaVisual)
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar detalle visual"))
      .finally(() => setTendenciaVisualLoading(false));
  }, [token, selectedTendenciaId]);

  const hasTrendDetails = useMemo(() => tendencias.length > 0, [tendencias]);
  const hasVisualData =
    (tendenciaVisual?.historico?.length ?? 0) > 0 && (tendenciaVisual?.tendencia?.length ?? 0) > 0;
  const chartLabels = useMemo(() => {
    if (!tendenciaVisual) return [];
    const labels = tendenciaVisual.historico.map((h) => h.fecha);
    if (tendenciaVisual.prediccion?.fecha) labels.push(tendenciaVisual.prediccion.fecha);
    return labels;
  }, [tendenciaVisual]);

  const chartData = useMemo(() => {
    if (!tendenciaVisual) return { labels: [], datasets: [] };

    const historicoMap = new Map(tendenciaVisual.historico.map((h) => [h.fecha, h.consumo]));
    const tendenciaMap = new Map(tendenciaVisual.tendencia.map((t) => [t.fecha, t.valor]));
    const predFecha = tendenciaVisual.prediccion?.fecha;
    const predValor = tendenciaVisual.prediccion?.valor;

    const consumoData = chartLabels.map((label) => historicoMap.get(label) ?? null);
    const tendenciaData = chartLabels.map((label) => {
      if (label === predFecha) return predValor ?? null;
      return tendenciaMap.get(label) ?? null;
    });
    const predData = chartLabels.map((label) => (label === predFecha ? predValor ?? null : null));

    return {
      labels: chartLabels,
      datasets: [
        {
          label: "Consumo real histórico",
          data: consumoData,
          borderColor: "rgb(59, 130, 246)",
          backgroundColor: "rgba(59, 130, 246, 0.25)",
          pointRadius: 3,
          tension: 0.15,
        },
        {
          label: "Línea de tendencia",
          data: tendenciaData,
          borderColor: "rgb(34, 197, 94)",
          backgroundColor: "rgba(34, 197, 94, 0.2)",
          borderDash: [6, 4],
          pointRadius: 2,
          spanGaps: true,
          tension: 0,
        },
        {
          label: "Predicción siguiente",
          data: predData,
          borderColor: "rgb(234, 88, 12)",
          backgroundColor: "rgb(234, 88, 12)",
          showLine: false,
          pointRadius: 6,
        },
      ],
    };
  }, [chartLabels, tendenciaVisual]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false as const,
      plugins: {
        legend: { position: "top" as const },
        title: { display: true, text: "Consumo histórico vs predicción" },
      },
      scales: {
        x: { title: { display: true, text: "Fechas" } },
        y: { title: { display: true, text: "Unidades consumidas" }, beginAtZero: true },
      },
    }),
    [],
  );

  if (!token) return null;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Corridas analíticas (ETL)</h3>

      {loading ? (
        <p className="text-sm text-gray-500">Cargando corridas ETL...</p>
      ) : error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Datos analizados</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Tendencias</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Task</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {corridas.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                    No hay corridas registradas.
                  </td>
                </tr>
              ) : (
                corridas.map((c) => (
                  <tr
                    key={c.id}
                    className={`hover:bg-gray-50 ${selectedCorridaId === c.id ? "bg-blue-50" : ""}`}
                    onClick={() => {
                      setSelectedCorridaId(c.id);
                      setSelectedTaskId(c.task_id);
                      setSelectedTendenciaId(null);
                      setTendenciaVisual(null);
                    }}
                  >
                    <td className="px-4 py-2 text-sm">{c.estado}</td>
                    <td className="px-4 py-2 text-sm">{fmtDate(c.fecha_ejecucion)}</td>
                    <td className="px-4 py-2 text-sm text-right">{c.registros_procesados}</td>
                    <td className="px-4 py-2 text-sm text-right">{c.resultados_tendencia_count}</td>
                    <td className="px-4 py-2 text-xs text-gray-500">{c.task_id || "N/A"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-4">
        <h4 className="text-sm font-semibold text-gray-700 uppercase mb-3">Detalle de tendencias lineales</h4>
        {tendenciasLoading ? (
          <p className="text-sm text-gray-500">Consultando resultados de tendencia...</p>
        ) : statusLoading ? (
          <p className="text-sm text-gray-500">Consultando estado de la corrida...</p>
        ) : !statusData && selectedTaskId ? (
          <p className="text-sm text-gray-500">Esperando estado de corrida...</p>
        ) : selectedCorridaId == null ? (
          <p className="text-sm text-gray-500">Seleccioná una corrida con task_id para ver detalle.</p>
        ) : hasTrendDetails ? (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodicidad</th>
                <th
                  className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase"
                  title="Cantidad de días usados para el cálculo"
                >
                  Días analizados
                </th>
                <th
                  className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase"
                  title="Cambio promedio del consumo por día"
                >
                  Variación diaria (unidades)
                </th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">R2</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Predicción sig.</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Rango</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Interpretación</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tendencias.map((t) => (
                <tr
                  key={t.id}
                  className={`cursor-pointer hover:bg-gray-50 ${
                    selectedTendenciaId === t.id ? "bg-blue-50" : ""
                  }`}
                  onClick={() => setSelectedTendenciaId(t.id)}
                >
                  <td className="px-4 py-2 text-sm">{t.producto_nombre}</td>
                  <td className="px-4 py-2 text-sm">{t.periodicidad}</td>
                  <td className="px-4 py-2 text-sm text-right">{t.puntos_usados}</td>
                  <td className="px-4 py-2 text-sm text-right">{fmtSigned(t.pendiente, 0)}</td>
                  <td className="px-4 py-2 text-sm text-right">{fmt(t.r2, 4)}</td>
                  <td className="px-4 py-2 text-sm text-right">{fmt(t.prediccion_siguiente, 2)}</td>
                  <td className="px-4 py-2 text-sm">
                    {t.fecha_inicio} - {t.fecha_fin}
                  </td>
                  <td className="px-4 py-2 text-sm">{tendenciaLabel(t.pendiente)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-gray-500">La corrida seleccionada no tiene resultados de tendencia.</p>
        )}

        {hasTrendDetails && (
          <div className="mt-4 border-t pt-4">
            {!tendenciaVisual ? (
              <p className="text-sm text-gray-500">Seleccioná una tendencia para ver su comparación.</p>
            ) : !hasVisualData ? (
              <p className="text-sm text-gray-500">
                {tendenciaVisual.detail || "No hay datos suficientes para visualizar la tendencia."}
              </p>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h5 className="text-sm font-semibold text-gray-700">
                    {tendenciaVisual.producto} ({tendenciaVisual.sku})
                  </h5>
                  {tendenciaVisualLoading && (
                    <span className="text-xs text-gray-500">Actualizando gráfico...</span>
                  )}
                </div>
                <p className="text-sm text-gray-600">
                  Predicción siguiente: {fmt(tendenciaVisual.prediccion?.valor, 2)} unidades
                </p>
                <div className="h-80">
                  <Line data={chartData} options={chartOptions} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
