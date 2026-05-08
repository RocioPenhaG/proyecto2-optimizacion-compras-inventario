/**
 * Sección "Hábitos de consumo" del dashboard (Release 2).
 * Consume /api/analytics/habitos-resumen/ y muestra gráficos y tablas.
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
import { formatIsoDateToDMY } from "@/utils/dateFormat";

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
const DIAS_SEMANA = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];

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
  const [mesSeleccionado, setMesSeleccionado] = useState<string>("");

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
  const consumo_mensual = data?.consumo_mensual ?? [];
  const consumo_por_dia_semana = data?.consumo_por_dia_semana ?? [];

  // Agrupar consumo mensual por (anio-mes) para el gráfico de barras (suma de todos los productos o por producto)
  const labelsMensualRaw = useMemo(
    () => Array.from(new Set(consumo_mensual.map((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}`))).sort(),
    [consumo_mensual],
  );
  const labelsMensualDisplay = useMemo(
    () =>
      labelsMensualRaw.map((ym) => {
        const [y, m] = ym.split("-");
        return `${m}-${y}`;
      }),
    [labelsMensualRaw],
  );
  const porMes = labelsMensualRaw.map((label) => {
    const total = consumo_mensual
      .filter((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}` === label)
      .reduce((s, r) => s + r.cantidad_total, 0);
    return total;
  });

  useEffect(() => {
    if (labelsMensualRaw.length === 0) {
      setMesSeleccionado("");
      return;
    }
    setMesSeleccionado((actual) =>
      actual && labelsMensualRaw.includes(actual) ? actual : labelsMensualRaw[labelsMensualRaw.length - 1] ?? "",
    );
  }, [labelsMensualRaw]);

  const chartMensual = useMemo(
    () => ({
      labels: labelsMensualDisplay,
      datasets: [
        {
          label: "Consumo total (unidades de productos)",
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
        legend: { position: "top" as const },
        title: { display: true, text: "Consumo mensual (total de unidades de productos por mes)" },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "Unidades de productos" } },
      },
    }),
    [],
  );

  // Por día de semana: agregar por dia_semana (1=Dom en Django ExtractWeekDay)
  const porDiaSemana = [1, 2, 3, 4, 5, 6, 7].map((d) => {
    const total = consumo_por_dia_semana
      .filter((r) => r.dia_semana === d)
      .reduce((s, r) => s + r.cantidad_total, 0);
    return total;
  });

  const chartDiaSemana = useMemo(
    () => ({
      labels: DIAS_SEMANA,
      datasets: [
        {
          label: "Consumo por día de la semana (unidades de productos)",
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
        legend: { position: "top" as const },
        title: { display: true, text: "Consumo por día de la semana (unidades de productos)" },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "Unidades de productos" } },
      },
    }),
    [],
  );

  const resumenPeriodo = useMemo(() => {
    const totalesMensuales = labelsMensualRaw.map((ym, idx) => ({
      ym,
      label: labelsMensualDisplay[idx],
      total: porMes[idx] ?? 0,
    }));
    const totalesDia = [1, 2, 3, 4, 5, 6, 7].map((dia) => ({
      dia,
      total: consumo_por_dia_semana
        .filter((r) => r.dia_semana === dia)
        .reduce((s, r) => s + r.cantidad_total, 0),
    }));
    const mesMayor = totalesMensuales.reduce<{ ym: string; label: string; total: number } | null>(
      (maximo, item) => (!maximo || item.total > maximo.total ? item : maximo),
      null,
    );
    const mesMenor = totalesMensuales.reduce<{ ym: string; label: string; total: number } | null>(
      (minimo, item) => (!minimo || item.total < minimo.total ? item : minimo),
      null,
    );
    const diaMayor = totalesDia.reduce<{ dia: number; total: number } | null>(
      (maximo, item) => (!maximo || item.total > maximo.total ? item : maximo),
      null,
    );
    const promedioMensual = totalesMensuales.length > 0
      ? totalesMensuales.reduce((sum, item) => sum + item.total, 0) / totalesMensuales.length
      : 0;

    return {
      mesMayor,
      mesMenor,
      diaMayor: diaMayor ? { nombre: DIAS_SEMANA[diaMayor.dia - 1], total: diaMayor.total } : null,
      promedioMensual,
    };
  }, [labelsMensualRaw, labelsMensualDisplay, porMes, consumo_por_dia_semana]);

  const productosMesSeleccionado = useMemo(() => {
    if (!mesSeleccionado) return [];
    const rows = consumo_mensual
      .filter((r) => `${r.anio}-${String(r.mes).padStart(2, "0")}` === mesSeleccionado)
      .sort((a, b) => b.cantidad_total - a.cantidad_total);
    const totalMes = rows.reduce((sum, r) => sum + r.cantidad_total, 0);

    const clasificar = (porcentaje: number): string => {
      if (porcentaje >= 20) return "Producto de alto consumo";
      if (porcentaje >= 10) return "Consumo relevante";
      return "Consumo moderado";
    };

    return rows.map((r) => {
      const porcentajeMes = totalMes > 0 ? (r.cantidad_total / totalMes) * 100 : 0;
      return {
        ...r,
        porcentajeMes,
        observacion: clasificar(porcentajeMes),
      };
    });
  }, [consumo_mensual, mesSeleccionado]);

  const totalMesSeleccionado = useMemo(() => {
    return productosMesSeleccionado.reduce((sum, p) => sum + p.cantidad_total, 0);
  }, [productosMesSeleccionado]);

  const formatearPorcentaje = (value: number) => {
    const redondeado = Math.round(value * 10) / 10;
    return Number.isInteger(redondeado) ? `${redondeado.toFixed(0)}%` : `${redondeado.toFixed(1)}%`;
  };

  const labelMesSeleccionado = useMemo(() => {
    if (!mesSeleccionado) return "—";
    const [anio, mes] = mesSeleccionado.split("-");
    return `${mes}-${anio}`;
  }, [mesSeleccionado]);

  return (
    <div className="space-y-6" data-testid="habitos-consumo-section">
      <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Hábitos de consumo</h3>
      {loading && (
        <p className="text-sm text-gray-500" data-testid="habitos-loading">
          Cargando hábitos de consumo...
        </p>
      )}
      {!loading && error && (
        <p className="text-sm text-red-500" data-testid="habitos-error">
          {error}
        </p>
      )}
      {!loading && !error && data && (
        <p className="text-sm text-gray-500">
          Período: {formatIsoDateToDMY(data.filtro_desde)} — {formatIsoDateToDMY(data.filtro_hasta)}
        </p>
      )}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-4 h-80" data-testid="habitos-chart-mensual">
            <Bar data={chartMensual} options={optsMensual} />
          </div>
          <div className="bg-white rounded-lg shadow p-4 h-80" data-testid="habitos-chart-dia-semana">
            <Bar data={chartDiaSemana} options={optsDiaSemana} />
          </div>
        </div>
      )}

      {!loading && !error && data && consumo_mensual.length === 0 && consumo_por_dia_semana.length === 0 && (
        <p className="text-sm text-gray-500" data-testid="habitos-sin-datos-periodo">
          No hay datos suficientes para analizar los hábitos de consumo en el período seleccionado.
        </p>
      )}

      {!loading && !error && data && consumo_mensual.length > 0 && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" data-testid="habitos-resumen-periodo">
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500">
              <p className="text-xs uppercase text-gray-500">Mes con mayor consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">
                {resumenPeriodo.mesMayor ? resumenPeriodo.mesMayor.label : "—"}
              </p>
              <p className="text-sm text-gray-600">
                {resumenPeriodo.mesMayor ? `${resumenPeriodo.mesMayor.total} unidades` : "Sin datos"}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-violet-500">
              <p className="text-xs uppercase text-gray-500">Mes con menor consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">
                {resumenPeriodo.mesMenor ? resumenPeriodo.mesMenor.label : "—"}
              </p>
              <p className="text-sm text-gray-600">
                {resumenPeriodo.mesMenor ? `${resumenPeriodo.mesMenor.total} unidades` : "Sin datos"}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-teal-500">
              <p className="text-xs uppercase text-gray-500">Día con mayor consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">
                {resumenPeriodo.diaMayor ? resumenPeriodo.diaMayor.nombre : "—"}
              </p>
              <p className="text-sm text-gray-600">
                {resumenPeriodo.diaMayor ? `${resumenPeriodo.diaMayor.total} unidades` : "Sin datos"}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-amber-500">
              <p className="text-xs uppercase text-gray-500">Promedio mensual de consumo</p>
              <p className="mt-2 text-base font-semibold text-gray-900">{Math.round(resumenPeriodo.promedioMensual)} unidades</p>
              <p className="text-sm text-gray-600">Promedio del período filtrado</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 flex flex-wrap items-center justify-between gap-3">
              <h4 className="text-sm font-medium text-gray-700">Productos más consumidos del mes seleccionado</h4>
              <div className="flex items-center gap-3">
                <p className="text-xs text-gray-500">{labelMesSeleccionado} · Total del mes: {totalMesSeleccionado} unidades</p>
                <label className="text-xs text-gray-600">
                  Mes:
                  <select
                    value={mesSeleccionado}
                    onChange={(e) => setMesSeleccionado(e.target.value)}
                    className="ml-2 border border-gray-300 rounded px-2 py-1 text-xs text-gray-700 bg-white"
                    data-testid="habitos-select-mes"
                  >
                    {[...labelsMensualRaw].reverse().map((ym) => {
                      const [anio, mes] = ym.split("-");
                      return (
                        <option key={ym} value={ym}>
                          {mes}-{anio}
                        </option>
                      );
                    })}
                  </select>
                </label>
              </div>
            </div>
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
                {productosMesSeleccionado.map((r) => (
                  <tr key={`${r.producto_id}-${r.anio}-${r.mes}`} className="hover:bg-gray-50">
                    <td className="px-6 py-2 text-sm text-gray-900">{r.producto_nombre}</td>
                    <td className="px-6 py-2 text-sm text-gray-600">{r.producto_sku}</td>
                    <td className="px-6 py-2 text-sm text-center">{r.cantidad_total}</td>
                    <td className="px-6 py-2 text-sm text-center">{formatearPorcentaje(r.porcentajeMes)}</td>
                    <td className="px-6 py-2 text-sm text-center">{r.promedio_diario.toFixed(2)}</td>
                    <td className="px-6 py-2 text-sm text-gray-700">
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                        {r.observacion}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {productosMesSeleccionado.length === 0 && (
              <p className="px-4 py-3 text-sm text-gray-500">
                No hay datos suficientes para analizar los hábitos de consumo en el período seleccionado.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
