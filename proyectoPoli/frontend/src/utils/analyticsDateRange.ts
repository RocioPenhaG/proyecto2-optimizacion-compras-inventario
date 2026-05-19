/** Presets de ventana temporal para el dashboard analítico. */

export type AnalyticsPeriodPreset = "7d" | "30d" | "90d" | "custom";



export const DEFAULT_RANGE_DAYS = 30;

export const MAX_CUSTOM_RANGE_DAYS = 30;

export const MAX_QUICK_RANGE_DAYS = 90;



export const ANALYTICS_PERIOD_DEFAULT: AnalyticsPeriodPreset = "30d";



export const ANALYTICS_PERIOD_OPTIONS: { id: AnalyticsPeriodPreset; label: string }[] = [

  { id: "7d", label: "Últimos 7 días" },

  { id: "30d", label: "Últimos 30 días" },

  { id: "90d", label: "Últimos 90 días" },

  { id: "custom", label: "Período personalizado" },

];



export const CUSTOM_RANGE_INFO_TEXT =

  "El período personalizado permite consultar hasta 30 días por vez.";



export interface AnalyticsDateRange {

  desde: string;

  hasta: string;

}



export function formatDateYYYYMMDD(d: Date): string {

  const y = d.getFullYear();

  const m = String(d.getMonth() + 1).padStart(2, "0");

  const day = String(d.getDate()).padStart(2, "0");

  return `${y}-${m}-${day}`;

}



function parseDateYYYYMMDD(iso: string): Date | null {

  const d = new Date(`${iso}T12:00:00`);

  return Number.isNaN(d.getTime()) ? null : d;

}



function addCalendarDays(d: Date, days: number): Date {

  const r = new Date(d);

  r.setDate(r.getDate() + days);

  return r;

}



function diffCalendarDays(desde: Date, hasta: Date): number {

  const ms = hasta.getTime() - desde.getTime();

  return Math.round(ms / 86400000);

}



/** Rango por preset rápido (7 / 30 / 90 días hasta hoy). */

export function getDateRangeFromPreset(

  preset: AnalyticsPeriodPreset,

  ref: Date = new Date(),

): AnalyticsDateRange {

  if (preset === "custom") {

    return getDefaultDateRange(ref);

  }

  const days = preset === "7d" ? 7 : preset === "90d" ? MAX_QUICK_RANGE_DAYS : DEFAULT_RANGE_DAYS;

  const hasta = new Date(ref);

  const desde = new Date(ref);

  desde.setDate(desde.getDate() - days);

  return { desde: formatDateYYYYMMDD(desde), hasta: formatDateYYYYMMDD(hasta) };

}



/** @deprecated Use getDateRangeFromPreset */

export const computeAnalyticsDateRange = getDateRangeFromPreset;



export function getDefaultDateRange(ref: Date = new Date()): AnalyticsDateRange {

  return getDateRangeFromPreset("30d", ref);

}



export function initialAnalyticsDateRange(): AnalyticsDateRange {

  return getDefaultDateRange();

}



/**

 * Acota un rango personalizado: máximo MAX_CUSTOM_RANGE_DAYS, hasta no mayor que hoy.

 * Si solo hay ``desde``, calcula hasta = desde + MAX_CUSTOM_RANGE_DAYS.

 */

export function clampCustomDateRange(

  desde: string,

  hasta?: string,

  ref: Date = new Date(),

): AnalyticsDateRange {

  const today = formatDateYYYYMMDD(ref);

  const desdeDate = parseDateYYYYMMDD(desde);

  if (!desdeDate) {

    return getDefaultDateRange(ref);

  }



  let hastaDate: Date;

  if (hasta) {

    hastaDate = parseDateYYYYMMDD(hasta) ?? addCalendarDays(desdeDate, MAX_CUSTOM_RANGE_DAYS);

  } else {

    hastaDate = addCalendarDays(desdeDate, MAX_CUSTOM_RANGE_DAYS);

  }



  const todayDate = parseDateYYYYMMDD(today)!;

  if (hastaDate > todayDate) {

    hastaDate = todayDate;

  }

  if (desdeDate > hastaDate) {

    return {

      desde: formatDateYYYYMMDD(hastaDate),

      hasta: formatDateYYYYMMDD(hastaDate),

    };

  }



  if (diffCalendarDays(desdeDate, hastaDate) > MAX_CUSTOM_RANGE_DAYS) {

    hastaDate = addCalendarDays(desdeDate, MAX_CUSTOM_RANGE_DAYS);

    if (hastaDate > todayDate) {

      hastaDate = todayDate;

    }

  }



  return {

    desde: formatDateYYYYMMDD(desdeDate),

    hasta: formatDateYYYYMMDD(hastaDate),

  };

}



/** Acota cualquier rango enviado al API (máx. 90 días para presets rápidos). */

export function clampQuickDateRange(desde: string, hasta: string, ref: Date = new Date()): AnalyticsDateRange {

  const desdeDate = parseDateYYYYMMDD(desde);

  const hastaDate = parseDateYYYYMMDD(hasta);

  if (!desdeDate || !hastaDate) {

    return getDefaultDateRange(ref);

  }

  const todayDate = parseDateYYYYMMDD(formatDateYYYYMMDD(ref))!;

  let h = hastaDate > todayDate ? todayDate : hastaDate;

  let d = desdeDate > h ? h : desdeDate;

  if (diffCalendarDays(d, h) > MAX_QUICK_RANGE_DAYS) {

    h = addCalendarDays(d, MAX_QUICK_RANGE_DAYS);

    if (h > todayDate) {

      h = todayDate;

      d = addCalendarDays(h, -MAX_QUICK_RANGE_DAYS);

    }

  }

  return { desde: formatDateYYYYMMDD(d), hasta: formatDateYYYYMMDD(h) };

}



export function analyticsPeriodInfoText(preset: AnalyticsPeriodPreset): string {

  if (preset === "7d") return "Mostrando datos de los últimos 7 días";

  if (preset === "90d") return "Mostrando datos de los últimos 90 días";

  if (preset === "custom") return CUSTOM_RANGE_INFO_TEXT;

  return "Mostrando datos de los últimos 30 días";

}



/** Meses calendario (YYYY-MM) entre dos fechas inclusive, ordenados ascendente. */

export function enumerateMonthsInRange(desde: string, hasta: string): string[] {

  if (!desde || !hasta) return [];

  const start = new Date(`${desde}T12:00:00`);

  const end = new Date(`${hasta}T12:00:00`);

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];



  const months: string[] = [];

  let year = start.getFullYear();

  let month = start.getMonth();

  const endYear = end.getFullYear();

  const endMonth = end.getMonth();



  while (year < endYear || (year === endYear && month <= endMonth)) {

    months.push(`${year}-${String(month + 1).padStart(2, "0")}`);

    month += 1;

    if (month > 11) {

      month = 0;

      year += 1;

    }

  }

  return months;

}

/** Query params obligatorios para APIs analíticas (siempre con rango acotado). */
export function buildAnalyticsQueryParams(desde: string, hasta: string): URLSearchParams {
  const params = new URLSearchParams();
  params.set("desde", desde);
  params.set("hasta", hasta);
  return params;
}

export function resolveAnalyticsQueryRange(desde?: string, hasta?: string): AnalyticsDateRange {
  if (desde && hasta) {
    return clampQuickDateRange(desde, hasta);
  }
  return getDefaultDateRange();
}

