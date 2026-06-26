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
  getAnalyticsCorridaTendencias,
  getAnalyticsTendenciaVisual,
  type CorridaAnalytics,
  type TendenciaLinealItem,
  type TendenciaVisualResponse,
} from "@/services/api";
import { formatIsoDateTimeToDMYHM, formatIsoDateToDMY } from "@/utils/dateFormat";
import { fmtUnidades as fmtUnidadesEnteras, roundUnidades } from "@/utils/unitsFormat";

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

function tendenciaInterpretacion(pendiente: unknown): string {
  const n = roundUnidades(pendiente);
  if (n == null) return "N/D";
  if (n > 0) return "Creciente";
  if (n < 0) return "Decreciente";
  return "Estable";
}

/** Etiquetas en español para `CorridaAnalitica.estado` (API devuelve claves en inglés). */
const CORRIDA_ESTADO_ES: Record<string, string> = {
  QUEUED: "En cola",
  RUNNING: "En ejecución",
  SUCCESS: "Completada",
  ERROR: "Error",
  CANCELLED: "Cancelada",
  OK: "Completada (histórico)",
};

function corridaEstadoLabel(estado: string | null | undefined): string {
  if (estado == null || estado === "") return "N/D";
  return CORRIDA_ESTADO_ES[estado] ?? estado;
}

/** Texto columna Tendencias: "X de Y productos analizados" o respaldo sin total. */
function textoTendenciasCorrida(
  resultadosCount: number,
  productosAnalizados: number | null | undefined,
): string {
  if (productosAnalizados != null && productosAnalizados > 0) {
    return `${resultadosCount} de ${productosAnalizados} productos analizados`;
  }
  if (resultadosCount === 1) return "1 producto con tendencia";
  if (resultadosCount > 1) return `${resultadosCount} productos con tendencia`;
  return "Sin tendencias";
}

function fmtUnidades(value: unknown): string {
  return fmtUnidadesEnteras(value, "N/D");
}

function fmtVariacionDiaria(value: unknown): string {
  const n = roundUnidades(value);
  if (n == null) return "N/D";
  if (n > 0) return `+${n}`;
  if (n === 0) return "+0";
  return String(n);
}

function fmtStockCelda(stockActual: number, stockMinimo: number): string {
  const actual = roundUnidades(stockActual) ?? 0;
  const minimo = roundUnidades(stockMinimo) ?? 0;
  return `${actual} / mín. ${minimo}`;
}

function fmtSugeridoReposicion(
  cantidad: number | null | undefined,
  criterio?: string | null,
): string {
  const n = roundUnidades(cantidad);
  if (n == null || n <= 0) return criterio?.trim() || "Stock suficiente";
  return `${n} unidades`;
}

const SUGERIDO_TOOLTIP =
  "El sugerido es orientativo y se calcula con stock mínimo, stock actual y tendencia inmediata.";

export function AnalyticsCorridasSection({ token }: AnalyticsCorridasSectionProps) {
  const [corridas, setCorridas] = useState<CorridaAnalytics[]>([]);
  const [selectedCorridaId, setSelectedCorridaId] = useState<number | null>(null);
  const [tendencias, setTendencias] = useState<TendenciaLinealItem[]>([]);
  const [selectedTendenciaId, setSelectedTendenciaId] = useState<number | null>(null);
  const [tendenciaVisual, setTendenciaVisual] = useState<TendenciaVisualResponse | null>(null);
  const [loading, setLoading] = useState(true);
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
        setSelectedCorridaId(firstCorrida?.id ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar corridas"))
      .finally(() => setLoading(false));
  }, [token]);

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

  const tendenciasOrdenadas = useMemo(() => {
    return [...tendencias].sort((a, b) => {
      const pa = roundUnidades(a.prediccion_siguiente) ?? 0;
      const pb = roundUnidades(b.prediccion_siguiente) ?? 0;
      return pb - pa;
    });
  }, [tendencias]);
  const hasVisualData =
    (tendenciaVisual?.historico?.length ?? 0) > 0 && (tendenciaVisual?.tendencia?.length ?? 0) > 0;
  const rawChartLabels = useMemo(() => {
    if (!tendenciaVisual) return [];
    const hist = tendenciaVisual.historico.map((h) => h.fecha);
    const predFecha = tendenciaVisual.prediccion?.fecha;
    if (predFecha && !hist.includes(predFecha)) return [...hist, predFecha];
    return hist;
  }, [tendenciaVisual]);

  const chartLabelsDisplay = useMemo(
    () => rawChartLabels.map((f) => formatIsoDateToDMY(f)),
    [rawChartLabels],
  );

  const chartData = useMemo(() => {
    if (!tendenciaVisual) return { labels: [], datasets: [] };

    const historicoMap = new Map(tendenciaVisual.historico.map((h) => [h.fecha, h.consumo]));
    const tendenciaMap = new Map(tendenciaVisual.tendencia.map((t) => [t.fecha, t.valor]));
    const predFecha = tendenciaVisual.prediccion?.fecha;
    const predValor = tendenciaVisual.prediccion?.valor;

    const consumoData = rawChartLabels.map((label) => roundUnidades(historicoMap.get(label)));
    const tendenciaData = rawChartLabels.map((label) => roundUnidades(tendenciaMap.get(label)));
    const predData = rawChartLabels.map((label) =>
      label === predFecha ? roundUnidades(predValor) : undefined,
    );

    return {
      labels: chartLabelsDisplay,
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
          label: "Estimación día siguiente (tendencia)",
          data: predData,
          borderColor: "rgb(234, 88, 12)",
          backgroundColor: "rgb(234, 88, 12)",
          showLine: false,
          pointRadius: 4,
        },
      ],
    };
  }, [rawChartLabels, chartLabelsDisplay, tendenciaVisual]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false as const,
      plugins: {
        legend: { position: "top" as const },
        title: { display: true, text: "Consumo histórico y tendencia lineal" },
        tooltip: {
          callbacks: {
            label(ctx: { dataset?: { label?: string }; parsed: { y: number | null } }) {
              const y = ctx.parsed.y;
              const base = ctx.dataset?.label ?? "";
              if (y == null || Number.isNaN(y)) return base;
              return `${base}: ${Math.round(y)}`;
            },
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "Fechas" } },
        y: {
          title: { display: true, text: "Unidades consumidas" },
          beginAtZero: true,
          ticks: {
            callback: (tickValue: string | number) =>
              typeof tickValue === "number" ? String(Math.round(tickValue)) : String(tickValue),
          },
        },
      },
    }),
    [],
  );

  if (!token) return null;

  return (
    <div id="seccion-corridas-etl" className="space-y-4 scroll-mt-4" data-testid="corridas-etl-section">
      <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Corridas analíticas (ETL)</h3>

      {loading ? (
        <p className="text-sm text-gray-500" data-testid="corridas-etl-loading">
          Cargando corridas ETL...
        </p>
      ) : error ? (
        <p className="text-sm text-red-500" data-testid="corridas-etl-error">
          {error}
        </p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200" data-testid="corridas-table">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Datos analizados</th>
                <th
                  className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase"
                  data-testid="corridas-header-tendencias"
                >
                  Tendencias
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {corridas.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-6 py-4 text-center text-sm text-gray-500"
                    data-testid="corridas-etl-empty"
                  >
                    No hay corridas registradas.
                  </td>
                </tr>
              ) : (
                corridas.map((c) => (
                  <tr
                    key={c.id}
                    data-testid={`corrida-row-${c.id}`}
                    className={`hover:bg-gray-50 ${selectedCorridaId === c.id ? "bg-blue-50" : ""}`}
                    onClick={() => {
                      setSelectedCorridaId(c.id);
                      setSelectedTendenciaId(null);
                      setTendenciaVisual(null);
                    }}
                  >
                    <td className="px-4 py-2 text-sm" data-testid={`estado-corrida-analitica-${c.id}`}>{corridaEstadoLabel(c.estado)}</td>
                    <td className="px-4 py-2 text-sm">{formatIsoDateTimeToDMYHM(c.fecha_ejecucion)}</td>
                    <td className="px-4 py-2 text-sm text-center">{c.registros_procesados}</td>
                    <td
                      className="px-4 py-2 text-sm text-center"
                      data-testid={`corrida-tendencias-count-${c.id}`}
                    >
                      {textoTendenciasCorrida(
                        c.resultados_tendencia_count,
                        c.productos_candidatos_tendencia,
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden" data-testid="tendencias-panel">
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Detalle de tendencias lineales
          </h4>
        </div>
        <div className="p-4">
        <p className="text-xs text-gray-500 mb-3 max-w-3xl" data-testid="tendencias-reposicion-aviso">
          La reposición sugerida es orientativa y se calcula a partir del stock actual, el stock mínimo
          configurado y la tendencia inmediata del consumo. No representa una orden automática de compra.
        </p>
        {tendenciasLoading ? (
          <p className="text-sm text-gray-500">Consultando resultados de tendencia...</p>
        ) : selectedCorridaId == null ? (
          <p className="text-sm text-gray-500" data-testid="tendencias-sin-corrida">
            Seleccioná una corrida para ver el detalle.
          </p>
        ) : hasTrendDetails ? (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200" data-testid="tendencias-table">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Stock</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodicidad</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                  Días analizados
                </th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                  Variación diaria (unidades)
                </th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">
                  Predicción sig.
                </th>
                <th
                  className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase"
                  title={SUGERIDO_TOOLTIP}
                >
                  Sugerido
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Rango</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Interpretación</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {tendenciasOrdenadas.map((t) => (
                <tr
                  key={t.id}
                  data-testid={`tendencia-row-${t.id}`}
                  className={`cursor-pointer hover:bg-sky-50 ${
                    selectedTendenciaId === t.id ? "bg-sky-100" : ""
                  }`}
                  onClick={() => setSelectedTendenciaId(t.id)}
                >
                  <td
                    className="px-4 py-2 text-sm text-left text-gray-900"
                    data-testid={`tendencia-producto-${t.id}`}
                  >
                    {t.producto_nombre}
                  </td>
                  <td
                    className="px-4 py-2 text-sm text-left text-gray-700 tabular-nums whitespace-nowrap"
                    data-testid={`tendencia-stock-${t.id}`}
                  >
                    {fmtStockCelda(t.stock_actual, t.stock_minimo)}
                  </td>
                  <td className="px-4 py-2 text-sm text-left text-gray-700">Diaria</td>
                  <td className="px-4 py-2 text-sm text-center text-gray-900 tabular-nums">
                    {roundUnidades(t.puntos_usados) ?? "N/D"}
                  </td>
                  <td
                    className="px-4 py-2 text-sm text-center text-gray-900 tabular-nums"
                    data-testid={`tendencia-variacion-${t.id}`}
                  >
                    {fmtVariacionDiaria(t.pendiente)}
                  </td>
                  <td
                    className="px-4 py-2 text-sm text-center text-gray-900 tabular-nums"
                    data-testid={`tendencia-prediccion-${t.id}`}
                  >
                    {fmtUnidades(t.prediccion_siguiente)}
                  </td>
                  <td
                    className="px-4 py-2 text-sm text-center text-gray-900 tabular-nums"
                    data-testid={`tendencia-sugerido-${t.id}`}
                    title={
                      (roundUnidades(t.cantidad_sugerida_reposicion) ?? 0) > 0
                        ? `${SUGERIDO_TOOLTIP} (${t.criterio_reposicion})`
                        : undefined
                    }
                  >
                    {fmtSugeridoReposicion(t.cantidad_sugerida_reposicion, t.criterio_reposicion)}
                  </td>
                  <td className="px-4 py-2 text-sm text-left text-gray-700 whitespace-nowrap">
                    {formatIsoDateToDMY(t.fecha_inicio)} - {formatIsoDateToDMY(t.fecha_fin)}
                  </td>
                  <td
                    className="px-4 py-2 text-sm text-left text-gray-900"
                    data-testid={`tendencia-interpretacion-${t.id}`}
                  >
                    {tendenciaInterpretacion(t.pendiente)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        ) : (
          <p className="text-sm text-gray-500" data-testid="tendencias-sin-resultados">
            La corrida seleccionada no tiene resultados de tendencia.
          </p>
        )}

        {hasTrendDetails && (
          <div className="mt-4 border-t pt-4">
            {!tendenciaVisual ? (
              <p className="text-sm text-gray-500" data-testid="tendencias-sin-seleccion-visual">
                Seleccioná una tendencia para ver su comparación.
              </p>
            ) : !hasVisualData ? (
              <p
                className="text-sm text-gray-500"
                data-testid="insufficient-data-message"
              >
                {tendenciaVisual.detail || "No hay datos suficientes para visualizar la tendencia."}
              </p>
            ) : (
              <div className="space-y-2" data-testid="tendencias-visual-panel">
                <div className="flex items-center justify-between gap-2">
                  <h5 className="text-sm font-semibold text-gray-700" data-testid="tendencias-visual-titulo">
                    {tendenciaVisual.producto} ({tendenciaVisual.sku})
                  </h5>
                  {tendenciaVisualLoading && (
                    <span className="text-xs text-gray-500">Actualizando gráfico...</span>
                  )}
                </div>
                <div className="text-sm text-gray-600 space-y-1" data-testid="tendencias-prediccion-texto">
                  <p>
                    Predicción día siguiente: {fmtUnidades(tendenciaVisual.prediccion?.valor)} unidades
                  </p>
                  <p className="text-xs text-gray-500">
                    La reposición de inventario debe evaluarse con stock actual, stock mínimo y criterio
                    operativo; este gráfico no sugiere cantidades de compra.
                  </p>
                </div>
                <div className="h-80" data-testid="tendencia-chart">
                  <Line data={chartData} options={chartOptions} />
                </div>
              </div>
            )}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
