import { useCallback, useEffect, useState } from "react";
import { useAccessToken } from "@/contexts/AuthContext";
import { AnalyticsCorridasSection } from "@/components/AnalyticsCorridasSection";
import { AnalyticsDashboardSection } from "@/components/AnalyticsDashboardSection";
import { AnalisisIntegralConsumoSection } from "@/components/AnalisisIntegralConsumoSection";
import { DashboardPeriodFilters } from "@/components/DashboardPeriodFilters";
import { RiskBadgeWithTooltip } from "@/components/RiskBadgeWithTooltip";
import { apiErrorMessage } from "@/utils/apiFetch";
import {
  type AnalyticsPeriodPreset,
  ANALYTICS_PERIOD_DEFAULT,
  buildAnalyticsQueryParams,
  clampCustomDateRange,
  getDateRangeFromPreset,
  initialAnalyticsDateRange,
} from "@/utils/analyticsDateRange";
import { formatIsoDateToDMY } from "@/utils/dateFormat";

const API_DASHBOARD = "/api/dashboard/";

interface DashboardData {
  solicitudes_por_estado: Record<string, number>;
  tiempo_promedio_aprobacion_dias: number;
  productos_stock_critico: number;
  stock_critico?: {
    resumen: {
      total_productos_criticos: number;
      total_sin_stock: number;
      total_cobertura_baja: number;
    };
    resultados: Array<{
      producto_id: number;
      nombre: string;
      sku: string;
      stock_actual: number;
      stock_minimo: number;
      cobertura_dias: number | null;
      cobertura_texto: string;
      riesgo: "Alto" | "Medio" | "Bajo";
      recomendacion: string;
    }>;
  };
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
  const initialRange = initialAnalyticsDateRange();
  const [periodPreset, setPeriodPreset] = useState<AnalyticsPeriodPreset>(ANALYTICS_PERIOD_DEFAULT);
  const [desdeDraft, setDesdeDraft] = useState(initialRange.desde);
  const [hastaDraft, setHastaDraft] = useState(initialRange.hasta);
  const [desdeFiltro, setDesdeFiltro] = useState(initialRange.desde);
  const [hastaFiltro, setHastaFiltro] = useState(initialRange.hasta);

  const applyPeriodPreset = useCallback((preset: AnalyticsPeriodPreset) => {
    setPeriodPreset(preset);
    if (preset === "custom") {
      const clamped = clampCustomDateRange(desdeDraft, hastaDraft);
      setDesdeDraft(clamped.desde);
      setHastaDraft(clamped.hasta);
      return;
    }
    const range = getDateRangeFromPreset(preset);
    setDesdeDraft(range.desde);
    setHastaDraft(range.hasta);
    setDesdeFiltro(range.desde);
    setHastaFiltro(range.hasta);
  }, [desdeDraft, hastaDraft]);

  const applyCustomDateFilter = useCallback(() => {
    const clamped = clampCustomDateRange(desdeDraft, hastaDraft);
    setDesdeDraft(clamped.desde);
    setHastaDraft(clamped.hasta);
    setDesdeFiltro(clamped.desde);
    setHastaFiltro(clamped.hasta);
  }, [desdeDraft, hastaDraft]);

  const fetchDashboard = async () => {
    if (!token) {
      setLoading(false);
      setError("Inicie sesión para ver el dashboard.");
      return;
    }
    const params = buildAnalyticsQueryParams(desdeFiltro, hastaFiltro);
    const url = `${API_DASHBOARD}?${params}`;
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
  }, [token, desdeFiltro, hastaFiltro]);

  if (loading) {
    return (
      <div className="text-gray-500" data-testid="dashboard-loading">
        Cargando dashboard...
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-red-500" data-testid="dashboard-error">
        {error}
      </div>
    );
  }
  if (!data) return null;
  const stockCritico = data.stock_critico;
  const stockCriticoResumen = stockCritico?.resumen;
  const stockCriticoRows = stockCritico?.resultados ?? [];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
        <DashboardPeriodFilters
          periodPreset={periodPreset}
          onPeriodChange={applyPeriodPreset}
          desdeDraft={desdeDraft}
          hastaDraft={hastaDraft}
          onDesdeDraftChange={(desde, hasta) => {
            setDesdeDraft(desde);
            setHastaDraft(hasta);
          }}
          onHastaDraftChange={(hasta) => {
            const clamped = clampCustomDateRange(desdeDraft, hasta);
            setHastaDraft(clamped.hasta);
          }}
          onApplyCustomDates={applyCustomDateFilter}
        />
      </div>

      <p className="text-sm text-gray-500" data-testid="dashboard-periodo-resumen">
        Mostrando datos del {formatIsoDateToDMY(desdeFiltro)} al {formatIsoDateToDMY(hastaFiltro)}
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
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500" data-testid="dashboard-stock-critico-card">
          <h3 className="text-sm font-medium text-gray-500 uppercase">PRODUCTOS CON STOCK CRÍTICO</h3>
          <p className="mt-2 text-2xl font-bold text-red-700">
            {stockCriticoResumen?.total_productos_criticos ?? data.productos_stock_critico} productos requieren atención
          </p>
          <div className="mt-2 text-sm text-gray-600 space-y-0.5">
            <p>Sin stock: {stockCriticoResumen?.total_sin_stock ?? 0}</p>
            <p>Stock para 7 días o menos: {stockCriticoResumen?.total_cobertura_baja ?? 0}</p>
          </div>
        </div>
      </div>

      <div
        className="bg-white rounded-lg shadow overflow-hidden"
        data-testid="dashboard-stock-critico-section"
      >
        <div className="p-4">
          {stockCriticoRows.length === 0 ? (
            <p className="text-sm text-gray-500" data-testid="dashboard-stock-critico-empty">
              No hay productos en estado crítico actualmente.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200" data-testid="dashboard-stock-critico-table">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Insumo</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Stock actual</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Stock mínimo</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Días estimados de stock</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Riesgo</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Recomendación</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {stockCriticoRows.map((row) => (
                    <tr key={row.producto_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-gray-900">{row.nombre}</div>
                        <div className="text-xs text-gray-500 mt-0.5">SKU {row.sku}</div>
                      </td>
                      <td className="px-4 py-3 text-sm text-center text-gray-900">{row.stock_actual}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-900">{row.stock_minimo}</td>
                      <td className="px-4 py-3 text-sm text-center text-gray-800">{row.cobertura_texto}</td>
                      <td className="px-4 py-3">
                        <RiskBadgeWithTooltip level={row.riesgo} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">{row.recomendacion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-6" data-testid="dashboard-analitico">
      <AnalyticsDashboardSection token={token} desde={desdeFiltro} hasta={hastaFiltro} />

      <AnalisisIntegralConsumoSection token={token} desde={desdeFiltro} hasta={hastaFiltro} />
      <AnalyticsCorridasSection token={token} />
      </div>
    </div>
  );
}
