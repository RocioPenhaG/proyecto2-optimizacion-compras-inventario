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
import { buildAnalyticsQueryParams, enumerateMonthsInRange } from "@/utils/analyticsDateRange";
import { formatIsoDateToDMY } from "@/utils/dateFormat";
import { getAnalyticsDemandaVsConsumo, type DemandaVsConsumoResponse } from "@/services/api";
import { RiskBadgeWithTooltip } from "@/components/RiskBadgeWithTooltip";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, BarController);

const API_HABITOS = "/api/analytics/habitos-resumen/";
const DIAS_SEMANA = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];

/** Títulos de tarjetas resumen (alineado con DemandaVsConsumoSection). */
const RESUMEN_CARD_TITLE = "text-xs font-medium text-gray-500 uppercase leading-snug";
const RESUMEN_TITLE_BLOCK = "h-12 flex shrink-0 items-start";

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
  dia_semana: number;
  cantidad_total: number;
}

interface HabitosData {
  consumo_mensual: ConsumoMensualItem[];
  consumo_por_dia_semana: ConsumoPorDiaItem[];
  filtro_desde: string | null;
  filtro_hasta: string | null;
  filtro_historico?: boolean;
}

interface Props {
  token: string | null;
  desde: string;
  hasta: string;
}

function habitoBadgeClass(habito: string): string {
  if (habito === "Consumo creciente") return "bg-violet-100 text-violet-800 border border-violet-200";
  if (habito === "Consumo frecuente") return "bg-indigo-100 text-indigo-800 border border-indigo-200";
  if (habito === "Consumo estable") return "bg-sky-100 text-sky-800 border border-sky-200";
  if (habito === "Consumo esporádico") return "bg-gray-100 text-gray-800 border border-gray-200";
  return "bg-slate-100 text-slate-700 border border-slate-200";
}

export function AnalisisIntegralConsumoSection({ token, desde, hasta }: Props) {
  const [habitos, setHabitos] = useState<HabitosData | null>(null);
  const [inteligente, setInteligente] = useState<DemandaVsConsumoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mesSeleccionado, setMesSeleccionado] = useState<string>("");
  const [tabActiva, setTabActiva] = useState<"productos_mes" | "analisis_inteligente">("analisis_inteligente");

  useEffect(() => {
    if (!token) return;
    const params = buildAnalyticsQueryParams(desde, hasta);
    const urlHabitos = `${API_HABITOS}?${params}`;
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(urlHabitos, { headers: { Authorization: `Bearer ${token}` } }).then(async (res) => {
        if (res.status === 403) throw new Error("No tiene permiso para ver análisis de consumo.");
        if (!res.ok) throw new Error("Error al cargar hábitos de consumo");
        return (await res.json()) as HabitosData;
      }),
      getAnalyticsDemandaVsConsumo(token, { desde, hasta, limit: 50 }),
    ])
      .then(([h, i]) => {
        setHabitos(h);
        setInteligente(i);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar análisis"))
      .finally(() => setLoading(false));
  }, [token, desde, hasta]);

  const consumo_mensual = habitos?.consumo_mensual ?? [];
  const consumo_por_dia_semana = habitos?.consumo_por_dia_semana ?? [];

  const labelsMensualRaw = useMemo(
    () => Array.from(new Set(consumo_mensual.map((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}`))).sort(),
    [consumo_mensual],
  );

  /** Meses del rango filtrado (calendario); en histórico, solo meses con datos. */
  const mesesEnPeriodo = useMemo(() => {
    if (desde && hasta) {
      const calendario = enumerateMonthsInRange(desde, hasta);
      if (calendario.length > 0) return calendario;
    }
    return labelsMensualRaw;
  }, [desde, hasta, labelsMensualRaw]);

  const mostrarSelectorMes = mesesEnPeriodo.length > 1;
  const labelsMensualDisplay = useMemo(
    () => labelsMensualRaw.map((ym) => {
      const [y, m] = ym.split("-");
      return `${m}-${y}`;
    }),
    [labelsMensualRaw],
  );
  const porMes = labelsMensualRaw.map((label) =>
    consumo_mensual
      .filter((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}` === label)
      .reduce((s, r) => s + r.cantidad_total, 0),
  );

  useEffect(() => {
    if (mesesEnPeriodo.length === 0) {
      setMesSeleccionado("");
      return;
    }
    const ymFrom = (iso: string) => (iso.length >= 7 ? iso.slice(0, 7) : null);
    const hastaYm = hasta ? ymFrom(hasta) : null;
    const preferred =
      (hastaYm && mesesEnPeriodo.includes(hastaYm) ? hastaYm : null) ||
      mesesEnPeriodo[mesesEnPeriodo.length - 1];
    setMesSeleccionado(preferred ?? "");
  }, [mesesEnPeriodo, hasta]);

  const chartMensual = useMemo(
    () => ({
      labels: labelsMensualDisplay,
      datasets: [
        {
          label: "Total mensual",
          data: porMes,
          backgroundColor: "rgba(59, 130, 246, 0.6)",
          borderColor: "rgb(59, 130, 246)",
          borderWidth: 1,
        },
      ],
    }),
    [labelsMensualDisplay, porMes],
  );

  const optsMensual = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false as const,
      plugins: {
        legend: { display: false },
        title: { display: false },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "Unidades",
            color: "#6b7280",
            font: { size: 12, weight: 500 },
            rotation: -90,
          },
        },
      },
    }),
    [],
  );

  const porDiaSemana = [1, 2, 3, 4, 5, 6, 7].map((d) =>
    consumo_por_dia_semana.filter((r) => r.dia_semana === d).reduce((s, r) => s + r.cantidad_total, 0),
  );
  const chartDiaSemana = useMemo(
    () => ({
      labels: DIAS_SEMANA,
      datasets: [
        {
          label: "Por día de la semana",
          data: porDiaSemana,
          backgroundColor: "rgba(34, 197, 94, 0.6)",
          borderColor: "rgb(34, 197, 94)",
          borderWidth: 1,
        },
      ],
    }),
    [porDiaSemana],
  );
  const optsDiaSemana = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false as const,
      plugins: {
        legend: { display: false },
        title: { display: false },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "Unidades",
            color: "#6b7280",
            font: { size: 12, weight: 500 },
            rotation: -90,
          },
        },
      },
    }),
    [],
  );

  const resumenPeriodo = useMemo(() => {
    const totalesMensuales = labelsMensualRaw.map((ym, idx) => ({ ym, label: labelsMensualDisplay[idx], total: porMes[idx] ?? 0 }));
    const totalesDia = [1, 2, 3, 4, 5, 6, 7].map((dia) => ({
      dia,
      total: consumo_por_dia_semana.filter((r) => r.dia_semana === dia).reduce((s, r) => s + r.cantidad_total, 0),
    }));
    const mesMayor = totalesMensuales.reduce<{ label: string; total: number } | null>(
      (m, it) => (!m || it.total > m.total ? { label: it.label, total: it.total } : m),
      null,
    );
    const mesMenor = totalesMensuales.reduce<{ label: string; total: number } | null>(
      (m, it) => (!m || it.total < m.total ? { label: it.label, total: it.total } : m),
      null,
    );
    const diaMayor = totalesDia.reduce<{ nombre: string; total: number } | null>(
      (m, it) => (!m || it.total > m.total ? { nombre: DIAS_SEMANA[it.dia - 1], total: it.total } : m),
      null,
    );
    const promedioMensual = totalesMensuales.length > 0 ? totalesMensuales.reduce((sum, i) => sum + i.total, 0) / totalesMensuales.length : 0;
    return { mesMayor, mesMenor, diaMayor, promedioMensual };
  }, [labelsMensualRaw, labelsMensualDisplay, porMes, consumo_por_dia_semana]);

  const productosMesSeleccionado = useMemo(() => {
    if (!mesSeleccionado) return [];
    const rows = consumo_mensual
      .filter((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}` === mesSeleccionado)
      .sort((a, b) => b.cantidad_total - a.cantidad_total);
    const totalMes = rows.reduce((sum, r) => sum + r.cantidad_total, 0);
    return rows.map((r) => {
      const porcentajeMes = totalMes > 0 ? (r.cantidad_total / totalMes) * 100 : 0;
      const observacion = porcentajeMes >= 20 ? "Producto de alto consumo" : porcentajeMes >= 10 ? "Consumo relevante" : "Consumo moderado";
      return { ...r, porcentajeMes, observacion };
    });
  }, [consumo_mensual, mesSeleccionado]);

  const totalMesSeleccionado = useMemo(
    () => productosMesSeleccionado.reduce((sum, p) => sum + p.cantidad_total, 0),
    [productosMesSeleccionado],
  );

  const lecturaPeriodo = useMemo(() => {
    const promedio = resumenPeriodo.promedioMensual || 0;
    const total = totalMesSeleccionado;
    const comparacion = promedio === 0
      ? "sin referencia de promedio mensual"
      : total > promedio * 1.2
        ? "por encima del promedio mensual"
        : total < promedio * 0.8
          ? "por debajo del promedio mensual"
          : "cercano al promedio mensual";
    const top1 = productosMesSeleccionado[0];
    const top3Pct = productosMesSeleccionado.slice(0, 3).reduce((sum, p) => sum + p.porcentajeMes, 0);
    const concentracion = top3Pct >= 70 ? "consumo concentrado en pocos insumos" : "consumo distribuido entre varios insumos";
    return {
      comparacion,
      top1Nombre: top1?.producto_nombre ?? "—",
      top1Pct: top1?.porcentajeMes ?? 0,
      top3Pct,
      concentracion,
    };
  }, [resumenPeriodo.promedioMensual, totalMesSeleccionado, productosMesSeleccionado]);

  const ocultarTarjetasMesExtremo = mesesEnPeriodo.length <= 1;

  const formatearPorcentaje = (value: number) => {
    const r = Math.round(value * 10) / 10;
    return Number.isInteger(r) ? `${r.toFixed(0)}%` : `${r.toFixed(1)}%`;
  };

  const labelMesSeleccionado = useMemo(() => {
    if (!mesSeleccionado) return "—";
    const [anio, mes] = mesSeleccionado.split("-");
    return `${mes}-${anio}`;
  }, [mesSeleccionado]);

  if (!token) return null;

  return (
    <div className="space-y-6" data-testid="analisis-integral-consumo-section">
      <div>
        <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Análisis integral de consumo</h3>
        <p className="mt-1 text-sm text-gray-500">
          Analiza patrones de consumo, demanda registrada, stock disponible y recomendaciones por insumo.
        </p>
        {!loading && !error && habitos && (
          <p className="text-sm text-gray-500 mt-2">
            <>
              Período: {formatIsoDateToDMY(habitos.filtro_desde ?? desde)} —{" "}
              {formatIsoDateToDMY(habitos.filtro_hasta ?? hasta)}
            </>
          </p>
        )}
      </div>

      {loading && (
        <p className="text-sm text-gray-500" data-testid="analisis-loading">
          Cargando análisis integral...
        </p>
      )}
      {!loading && error && (
        <p className="text-sm text-red-500" data-testid="analisis-error">
          {error}
        </p>
      )}

      {!loading && !error && habitos &&
        consumo_mensual.length === 0 &&
        consumo_por_dia_semana.length === 0 && (
          <p
            className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
            data-testid="analisis-sin-datos-periodo"
          >
            No hay datos suficientes para analizar el consumo en el período seleccionado.
          </p>
        )}

      {!loading && !error && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4" data-testid="analisis-chart-mensual">
              <h4 className="text-sm font-bold text-gray-800 mb-3">Consumo mensual</h4>
              <div className="h-80">
                <Bar data={chartMensual} options={optsMensual} />
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4" data-testid="analisis-chart-dia-semana">
              <h4 className="text-sm font-bold text-gray-800 mb-3">Consumo por día de la semana</h4>
              <div className="h-80">
                <Bar data={chartDiaSemana} options={optsDiaSemana} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" data-testid="analisis-resumen-periodo">
            {!ocultarTarjetasMesExtremo && (
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500">
                <p className="text-xs uppercase text-gray-500">Mes con mayor consumo</p>
                <p className="mt-2 text-base font-semibold text-gray-900">{resumenPeriodo.mesMayor?.label ?? "—"}</p>
                <p className="text-sm text-gray-600">{resumenPeriodo.mesMayor ? `${resumenPeriodo.mesMayor.total} unidades` : "Sin datos"}</p>
              </div>
            )}
            {!ocultarTarjetasMesExtremo && (
              <div className="bg-white rounded-lg shadow p-4 border-l-4 border-violet-500">
                <p className="text-xs uppercase text-gray-500">Mes con menor consumo</p>
                <p className="mt-2 text-base font-semibold text-gray-900">{resumenPeriodo.mesMenor?.label ?? "—"}</p>
                <p className="text-sm text-gray-600">{resumenPeriodo.mesMenor ? `${resumenPeriodo.mesMenor.total} unidades` : "Sin datos"}</p>
              </div>
            )}
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-teal-500">
              <p className="text-xs uppercase text-gray-500">Día con mayor consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">{resumenPeriodo.diaMayor?.nombre ?? "—"}</p>
              <p className="text-sm text-gray-600">{resumenPeriodo.diaMayor ? `${resumenPeriodo.diaMayor.total} unidades` : "Sin datos"}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500">
              <p className="text-xs uppercase text-gray-500">Promedio mensual de consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">{Math.round(resumenPeriodo.promedioMensual)} unidades</p>
              <p className="text-sm text-gray-600">Promedio del período filtrado</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4 border border-gray-100" data-testid="analisis-lectura-periodo">
            <h4 className="text-sm font-medium text-gray-700 uppercase">Lectura del período</h4>
            <ul className="mt-3 text-sm text-gray-700 space-y-1">
              <li>El mes seleccionado tuvo {totalMesSeleccionado} unidades consumidas.</li>
              <li>Este valor está {lecturaPeriodo.comparacion}.</li>
              <li>El producto más representativo del mes fue {lecturaPeriodo.top1Nombre}, con {formatearPorcentaje(lecturaPeriodo.top1Pct)} del consumo mensual.</li>
              <li>Los 3 productos principales concentran {formatearPorcentaje(lecturaPeriodo.top3Pct)} del consumo del mes.</li>
              <li>Esto indica un {lecturaPeriodo.concentracion} durante el período seleccionado.</li>
            </ul>
          </div>

          <div className="bg-white rounded-lg shadow overflow-hidden" data-testid="analisis-por-producto">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
              <h4 className="text-sm font-medium text-gray-700 uppercase">Análisis por producto</h4>
              <div className="mt-3 inline-flex rounded-md border border-gray-200 overflow-hidden" data-testid="analisis-tabs">
                <button
                  type="button"
                  data-testid="analisis-tab-inteligente"
                  onClick={() => setTabActiva("analisis_inteligente")}
                  className={`px-3 py-1.5 text-sm ${tabActiva === "analisis_inteligente" ? "bg-indigo-600 text-white" : "bg-white text-gray-700 hover:bg-gray-50"}`}
                >
                  Análisis inteligente
                </button>
                <button
                  type="button"
                  data-testid="analisis-tab-productos-mes"
                  onClick={() => setTabActiva("productos_mes")}
                  className={`px-3 py-1.5 text-sm border-l border-gray-200 ${tabActiva === "productos_mes" ? "bg-indigo-600 text-white" : "bg-white text-gray-700 hover:bg-gray-50"}`}
                >
                  Productos más consumidos del mes
                </button>
              </div>
            </div>

            <div className="p-4">
              {tabActiva === "productos_mes" && (
                <div className="space-y-3" data-testid="analisis-tab-productos-mes-panel">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-gray-500">{labelMesSeleccionado} · Total del mes: {totalMesSeleccionado} unidades</p>
                    {mostrarSelectorMes && (
                      <label className="text-xs text-gray-600">
                        Mes:
                        <select
                          data-testid="analisis-mes-select"
                          value={mesSeleccionado}
                          onChange={(e) => setMesSeleccionado(e.target.value)}
                          className="ml-2 border border-gray-300 rounded px-2 py-1 text-xs text-gray-700 bg-white"
                        >
                          {[...mesesEnPeriodo].reverse().map((ym) => {
                            const [anio, mes] = ym.split("-");
                            return <option key={ym} value={ym}>{mes}-{anio}</option>;
                          })}
                        </select>
                      </label>
                    )}
                  </div>
                  <div className="overflow-x-auto rounded-lg border border-gray-200" data-testid="analisis-productos-mes-tabla">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Producto</th>
                          <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
                          <th className="px-6 py-2 text-center text-xs font-medium text-gray-500 uppercase">Cantidad consumida</th>
                          <th className="px-6 py-2 text-center text-xs font-medium text-gray-500 uppercase">% del total del mes</th>
                          <th className="px-6 py-2 text-center text-xs font-medium text-gray-500 uppercase">Promedio diario</th>
                          <th className="px-6 py-2 text-left text-xs font-medium text-gray-500 uppercase">Observación</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {productosMesSeleccionado.length === 0 && (
                          <tr>
                            <td colSpan={6} className="px-6 py-4 text-sm text-center text-gray-500">
                              Sin consumo registrado en este mes dentro del período filtrado.
                            </td>
                          </tr>
                        )}
                        {productosMesSeleccionado.map((r) => (
                          <tr key={`${r.producto_id}-${r.anio}-${r.mes}`} className="hover:bg-gray-50">
                            <td className="px-6 py-2 text-sm text-gray-900">{r.producto_nombre}</td>
                            <td className="px-6 py-2 text-sm text-gray-600">{r.producto_sku}</td>
                            <td className="px-6 py-2 text-sm text-center">{r.cantidad_total}</td>
                            <td className="px-6 py-2 text-sm text-center">{formatearPorcentaje(r.porcentajeMes)}</td>
                            <td className="px-6 py-2 text-sm text-center">{r.promedio_diario.toFixed(2)}</td>
                            <td className="px-6 py-2 text-sm text-gray-700"><span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{r.observacion}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {tabActiva === "analisis_inteligente" && (
                <div className="space-y-4" data-testid="analisis-tab-inteligente-panel">
                  {!inteligente || inteligente.resultados.length === 0 ? (
                    <p className="text-sm text-gray-500" data-testid="analisis-inteligente-empty">
                      No hay datos suficientes para generar el análisis inteligente en el período seleccionado.
                    </p>
                  ) : (
                    <>
                      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 items-stretch" data-testid="analisis-inteligente-resumen">
                        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500 flex flex-col h-full">
                          <div className={RESUMEN_TITLE_BLOCK}>
                            <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Riesgo alto de desabastecimiento</p>
                          </div>
                          <p className="mt-3 text-xl font-bold text-gray-900 shrink-0 tabular-nums">
                            {inteligente.resumen.riesgo_alto} insumos
                          </p>
                          <p className="text-xs text-gray-500 mt-1">Requieren atención urgente por bajo stock o baja cobertura.</p>
                        </div>
                        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-violet-500 flex flex-col h-full">
                          <div className={RESUMEN_TITLE_BLOCK}>
                            <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Se consume más de lo solicitado</p>
                          </div>
                          <p className="mt-3 text-xl font-bold text-gray-900 shrink-0 tabular-nums">
                            {inteligente.resumen.consumo_mayor_solicitud} insumos
                          </p>
                          <p className="text-xs text-gray-500 mt-1">El consumo real supera la cantidad pedida por las áreas.</p>
                        </div>
                        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500 flex flex-col h-full">
                          <div className={RESUMEN_TITLE_BLOCK}>
                            <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Solicitud y consumo coinciden</p>
                          </div>
                          <p className="mt-3 text-xl font-bold text-amber-950 shrink-0 tabular-nums">
                            {inteligente.resumen.demanda_coherente} insumos
                          </p>
                          <p className="text-xs text-gray-500 mt-1">La demanda registrada coincide razonablemente con el consumo real.</p>
                        </div>
                        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-500 flex flex-col h-full">
                          <div className={RESUMEN_TITLE_BLOCK}>
                            <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Stock para pocos días</p>
                          </div>
                          <p className="mt-3 text-xl font-bold text-red-950 shrink-0 tabular-nums">
                            {inteligente.resumen.baja_cobertura} insumos
                          </p>
                          <p className="text-xs text-gray-500 mt-1">Tienen cobertura estimada menor o igual a 7 días.</p>
                        </div>
                        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-emerald-500 flex flex-col h-full">
                          <div className={RESUMEN_TITLE_BLOCK}>
                            <p className={`${RESUMEN_CARD_TITLE} line-clamp-2`}>Se solicita más de lo consumido</p>
                          </div>
                          <p className="mt-3 text-xl font-bold text-emerald-950 shrink-0 tabular-nums">
                            {inteligente.resumen.mayor_solicitud_consumo} insumos
                          </p>
                          <p className="text-xs text-gray-500 mt-1">Las áreas pidieron más de lo que finalmente se consumió.</p>
                        </div>
                      </div>

                      <div className="overflow-x-auto rounded-lg border border-gray-200" data-testid="analisis-inteligente-tabla">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Insumo</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Demanda vs consumo</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Hábito detectado</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Días estimados de stock</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Riesgo</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Recomendación</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-200">
                            {inteligente.resultados.map((row) => (
                              <tr key={row.producto_id} data-testid={`analisis-inteligente-row-${row.producto_id}`} className="hover:bg-gray-50">
                                <td className="px-4 py-3">
                                  <div className="text-sm font-medium text-gray-900">{row.nombre}</div>
                                  <div className="text-xs text-gray-500 mt-0.5">SKU {row.sku}</div>
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-800">{row.demanda_vs_consumo}</td>
                                <td className="px-4 py-3">
                                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${habitoBadgeClass(row.habito_detectado)}`}>{row.habito_detectado}</span>
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-800">{row.cobertura_texto}</td>
                                <td className="px-4 py-3">
                                  <RiskBadgeWithTooltip level={row.riesgo} />
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-700">{row.recomendacion}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
