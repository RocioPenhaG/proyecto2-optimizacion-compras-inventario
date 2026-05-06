/**
 * Panel de integración analítica: KPIs desde HechoConsumo/ResumenConsumoMensual,
 * top productos consumidos y estado de la última corrida ETL (CorridaAnalitica).
 */
import { useEffect, useMemo, useState } from "react";
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
import {
  getAnalyticsResumenConsumo,
  getAnalyticsTopProductosConsumidos,
  getAnalyticsUltimaCorrida,
  type ResumenConsumoResponse,
  type TopProductosConsumidosResponse,
  type UltimaCorridaResponse,
} from "@/services/api";
import { formatIsoDateTimeToDMYHM, formatIsoDateToDMY } from "@/utils/dateFormat";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, BarController);

const CORRIDA_ESTADO_ES: Record<string, string> = {
  QUEUED: "En cola",
  RUNNING: "En ejecución",
  SUCCESS: "Completada",
  ERROR: "Error",
  CANCELLED: "Cancelada",
  OK: "Completada (histórico)",
};

const METODO_ES: Record<string, string> = {
  MANUAL: "Manual",
  SCHEDULED: "Programada (Beat)",
  API: "API",
  RETRY: "Reintento",
};

interface AnalyticsDashboardSectionProps {
  token: string | null;
  desde: string;
  hasta: string;
}

export function AnalyticsDashboardSection({ token, desde, hasta }: AnalyticsDashboardSectionProps) {
  const [resumen, setResumen] = useState<ResumenConsumoResponse | null>(null);
  const [top, setTop] = useState<TopProductosConsumidosResponse | null>(null);
  const [ultima, setUltima] = useState<UltimaCorridaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const opts = { desde: desde || undefined, hasta: hasta || undefined };
    Promise.all([
      getAnalyticsResumenConsumo(token, opts.desde, opts.hasta),
      getAnalyticsTopProductosConsumidos(token, { ...opts, limit: 10 }),
      getAnalyticsUltimaCorrida(token),
    ])
      .then(([r, t, u]) => {
        setResumen(r);
        setTop(t);
        setUltima(u);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar datos analíticos"))
      .finally(() => setLoading(false));
  }, [token, desde, hasta]);

  const chartTop = useMemo(() => {
    const rows = top?.top_productos ?? [];
    const labels = rows.map((r) => `${r.producto_sku}`);
    const data = rows.map((r) => r.cantidad_total);
    return {
      labels,
      datasets: [
        {
          label: "Unidades consumidas (OUT)",
          data,
          backgroundColor: "rgba(99, 102, 241, 0.65)",
          borderColor: "rgb(79, 70, 229)",
          borderWidth: 1,
        },
      ],
    };
  }, [top]);

  const chartTopOptions = useMemo(
    () => ({
      indexAxis: "y" as const,
      responsive: true,
      maintainAspectRatio: false,
      animation: false as const,
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Productos más consumidos (salidas)" },
      },
      scales: {
        x: { beginAtZero: true, title: { display: true, text: "Cantidad" } },
      },
    }),
    [],
  );

  if (!token) return null;

  const c = ultima?.corrida;

  return (
    <div className="space-y-6" data-testid="analytics-dashboard-section">
      <div>
        <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Indicadores analíticos (consumo)</h3>
        <p className="text-sm text-gray-500 mt-1">
          Datos desde tablas generadas por el ETL (HechoConsumo, ResumenConsumoMensual). Mismo período que los
          filtros del dashboard.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-500" data-testid="analytics-loading">
          Cargando indicadores analíticos...
        </p>
      )}
      {!loading && error && (
        <p className="text-sm text-red-500" data-testid="analytics-error">
          {error}
        </p>
      )}

      {!loading && !error && resumen && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="analytics-kpi-grid">
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500" data-testid="analytics-kpi-total-salidas">
              <h4 className="text-xs font-medium text-gray-500 uppercase">Total salidas (período)</h4>
              <p className="mt-2 text-2xl font-bold text-gray-900">{resumen.total_salidas.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-violet-500" data-testid="analytics-kpi-productos-consumo">
              <h4 className="text-xs font-medium text-gray-500 uppercase">Productos con consumo</h4>
              <p className="mt-2 text-2xl font-bold text-gray-900">{resumen.productos_distintos}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-teal-500" data-testid="analytics-kpi-dias-out">
              <h4 className="text-xs font-medium text-gray-500 uppercase">Días con movimiento OUT</h4>
              <p className="mt-2 text-2xl font-bold text-gray-900">{resumen.dias_con_consumo}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500" data-testid="analytics-kpi-promedio-diario">
              <h4 className="text-xs font-medium text-gray-500 uppercase">Promedio diario (período)</h4>
              <p className="mt-2 text-2xl font-bold text-gray-900">{resumen.promedio_diario_periodo}</p>
              <p className="text-xs text-gray-500 mt-1">Total salidas ÷ días con consumo</p>
            </div>
          </div>

          {resumen.total_salidas === 0 && (
            <p
              className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
              data-testid="analytics-no-salidas-banner"
            >
              No hay salidas (OUT) registradas en HechoConsumo para este período. Ejecute el ETL analítico si ya
              hay movimientos de stock.
            </p>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4 h-96" data-testid="analytics-top-consumidos-chart">
              {(top?.top_productos.length ?? 0) === 0 ? (
                <p
                  className="text-sm text-gray-500 h-full flex items-center justify-center"
                  data-testid="analytics-top-consumidos-empty"
                >
                  Sin datos para el gráfico de ranking en el período seleccionado.
                </p>
              ) : (
                <Bar data={chartTop} options={chartTopOptions} />
              )}
            </div>

            <div className="bg-white rounded-lg shadow p-4 border border-gray-100" data-testid="analytics-ultima-corrida">
              <h4 className="text-sm font-semibold text-gray-700 uppercase mb-3">Última corrida ETL</h4>
              {!c ? (
                <p className="text-sm text-gray-500">Aún no hay corridas analíticas registradas.</p>
              ) : (
                <dl className="text-sm space-y-2">
                  <div className="flex justify-between gap-2">
                    <dt className="text-gray-500">Estado</dt>
                    <dd className="font-medium text-gray-900">{CORRIDA_ESTADO_ES[c.estado] ?? c.estado}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-gray-500">Método</dt>
                    <dd className="text-gray-900">{c.metodo ? METODO_ES[c.metodo] ?? c.metodo : "—"}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-gray-500">Ejecución</dt>
                    <dd className="text-gray-900 text-right">{formatIsoDateTimeToDMYHM(c.fecha_ejecucion)}</dd>
                  </div>
                  {(c.fecha_desde || c.fecha_hasta) && (
                    <div className="flex justify-between gap-2">
                      <dt className="text-gray-500">Rango procesado</dt>
                      <dd className="text-gray-900 text-right">
                        {formatIsoDateToDMY(c.fecha_desde ?? undefined)} →{" "}
                        {formatIsoDateToDMY(c.fecha_hasta ?? undefined)}
                      </dd>
                    </div>
                  )}
                  <div className="flex justify-between gap-2">
                    <dt className="text-gray-500">Registros</dt>
                    <dd className="font-mono text-gray-900">{c.registros_procesados}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-gray-500">Tendencias calculadas</dt>
                    <dd className="text-gray-900">{c.resultados_tendencia_count}</dd>
                  </div>
                  {c.mensaje && (
                    <div className="pt-2 border-t border-gray-100">
                      <dt className="text-gray-500 mb-1">Mensaje</dt>
                      <dd className="text-gray-700 text-xs leading-relaxed">{c.mensaje}</dd>
                    </div>
                  )}
                  {c.estado === "ERROR" && c.error_detalle && (
                    <div className="pt-2 text-xs text-red-600">{c.error_detalle}</div>
                  )}
                </dl>
              )}
              <a
                href="#seccion-corridas-etl"
                className="text-xs text-indigo-600 hover:underline mt-4 inline-block"
              >
                Ver historial de corridas y tendencias →
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
