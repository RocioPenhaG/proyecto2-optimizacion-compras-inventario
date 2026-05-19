/**
 * Sección de análisis interpretativo para compras/inventario.
 */
import { useEffect, useState } from "react";
import { getAnalyticsDemandaVsConsumo, type DemandaVsConsumoResponse } from "@/services/api";
import { RiskBadgeWithTooltip } from "@/components/RiskBadgeWithTooltip";

/** Títulos de las tarjetas resumen (mismo tono que las primeras cards). */
const RESUMEN_CARD_TITLE = "text-xs font-medium text-gray-500 uppercase leading-snug";

/** Altura fija del encabezado para alinear contadores entre columnas (hasta 2 líneas). */
const RESUMEN_TITLE_BLOCK = "h-12 flex shrink-0 items-start";

function habitoBadgeClass(habito: string): string {
  if (habito === "Consumo creciente") return "bg-violet-100 text-violet-800 border border-violet-200";
  if (habito === "Consumo frecuente") return "bg-indigo-100 text-indigo-800 border border-indigo-200";
  if (habito === "Consumo estable") return "bg-sky-100 text-sky-800 border border-sky-200";
  if (habito === "Consumo esporádico") return "bg-gray-100 text-gray-800 border border-gray-200";
  return "bg-slate-100 text-slate-700 border border-slate-200";
}

interface DemandaVsConsumoSectionProps {
  token: string | null;
  desde: string;
  hasta: string;
}

export function DemandaVsConsumoSection({ token, desde, hasta }: DemandaVsConsumoSectionProps) {
  const [data, setData] = useState<DemandaVsConsumoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getAnalyticsDemandaVsConsumo(token, {
      desde: desde || undefined,
      hasta: hasta || undefined,
      limit: 50,
    })
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar la comparación"))
      .finally(() => setLoading(false));
  }, [token, desde, hasta]);

  if (!token) return null;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden" data-testid="demanda-vs-consumo-section">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
        <h3 className="text-sm font-medium text-gray-700 uppercase">Análisis inteligente de demanda y consumo</h3>
      </div>

      <div className="p-4">
        {loading && (
          <p className="text-sm text-gray-500" data-testid="demanda-vs-consumo-loading">
            Cargando comparación...
          </p>
        )}
        {!loading && error && (
          <p className="text-sm text-red-600" data-testid="demanda-vs-consumo-error">
            {error}
          </p>
        )}
        {!loading && !error && data && data.resultados.length === 0 && (
          <p className="text-sm text-gray-500" data-testid="demanda-vs-consumo-empty">
            No hay datos suficientes para generar el análisis inteligente en el período seleccionado.
          </p>
        )}
        {!loading && !error && data && data.resultados.length > 0 && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6 items-stretch">
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500 flex flex-col h-full">
                <div className={RESUMEN_TITLE_BLOCK}>
                  <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Riesgo alto de desabastecimiento</p>
                </div>
                <p className="mt-3 text-2xl font-bold text-gray-900 shrink-0 tabular-nums">
                  {data.resumen.riesgo_alto.toLocaleString()}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-violet-500 flex flex-col h-full">
                <div className={RESUMEN_TITLE_BLOCK}>
                  <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Consumo mayor a solicitud</p>
                </div>
                <p className="mt-3 text-2xl font-bold text-gray-900 shrink-0 tabular-nums">
                  {data.resumen.consumo_mayor_solicitud.toLocaleString()}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500 flex flex-col h-full">
                <div className={RESUMEN_TITLE_BLOCK}>
                  <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Demanda coherente</p>
                </div>
                <p className="mt-3 text-2xl font-bold text-amber-950 shrink-0 tabular-nums">{data.resumen.demanda_coherente}</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500 flex flex-col h-full">
                <div className={RESUMEN_TITLE_BLOCK}>
                  <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Stock para pocos días</p>
                </div>
                <p className="mt-3 text-2xl font-bold text-red-950 shrink-0 tabular-nums">
                  {data.resumen.baja_cobertura}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-emerald-500 flex flex-col h-full">
                <div className={RESUMEN_TITLE_BLOCK}>
                  <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Mayor solicitud que consumo</p>
                </div>
                <p className="mt-3 text-2xl font-bold text-emerald-950 shrink-0 tabular-nums">{data.resumen.mayor_solicitud_consumo}</p>
              </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Insumo</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Demanda vs consumo</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Hábito detectado</th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Cobertura</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Riesgo</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Recomendación</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.resultados.map((row) => {
                    return (
                      <tr key={row.producto_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900">{row.nombre}</div>
                          <div className="text-xs text-gray-500 mt-0.5">SKU {row.sku}</div>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-800">
                          <div>{row.demanda_vs_consumo}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${habitoBadgeClass(row.habito_detectado)}`}
                          >
                            {row.habito_detectado}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-center text-gray-700">{row.cobertura_texto}</td>
                        <td className="px-4 py-3">
                          <RiskBadgeWithTooltip level={row.riesgo} />
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {row.recomendacion}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
