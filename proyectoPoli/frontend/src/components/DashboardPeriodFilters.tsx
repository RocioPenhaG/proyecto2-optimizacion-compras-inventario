import {

  ANALYTICS_PERIOD_OPTIONS,

  CUSTOM_RANGE_INFO_TEXT,

  type AnalyticsPeriodPreset,

  analyticsPeriodInfoText,

  clampCustomDateRange,

} from "@/utils/analyticsDateRange";



interface DashboardPeriodFiltersProps {

  periodPreset: AnalyticsPeriodPreset;

  onPeriodChange: (preset: AnalyticsPeriodPreset) => void;

  desdeDraft: string;

  hastaDraft: string;

  onDesdeDraftChange: (desde: string, hasta: string) => void;

  onHastaDraftChange: (hasta: string) => void;

  onApplyCustomDates: () => void;

}



export function DashboardPeriodFilters({

  periodPreset,

  onPeriodChange,

  desdeDraft,

  hastaDraft,

  onDesdeDraftChange,

  onHastaDraftChange,

  onApplyCustomDates,

}: DashboardPeriodFiltersProps) {

  const isCustom = periodPreset === "custom";



  return (

    <div className="flex flex-col items-end gap-2" data-testid="dashboard-period-filters">

      <div className="flex flex-wrap items-center justify-end gap-2">

        <p className="text-sm text-gray-600" data-testid="analytics-period-info">

          {analyticsPeriodInfoText(periodPreset)}

        </p>

        <label className="text-sm text-gray-600 flex items-center gap-2">

          Período:

          <select

            value={periodPreset}

            onChange={(e) => onPeriodChange(e.target.value as AnalyticsPeriodPreset)}

            className="border border-gray-300 rounded px-2 py-1.5 text-sm text-gray-700 bg-white min-w-[10rem]"

            data-testid="analytics-period-select"

          >

            {ANALYTICS_PERIOD_OPTIONS.map((opt) => (

              <option key={opt.id} value={opt.id}>

                {opt.label}

              </option>

            ))}

          </select>

        </label>

      </div>



      {isCustom && (

        <div

          className="flex flex-col items-end gap-2 max-w-md"

          data-testid="dashboard-filtro-fechas-panel"

        >

          <p className="text-xs text-gray-500 text-right">{CUSTOM_RANGE_INFO_TEXT}</p>

          <div className="flex flex-wrap items-center justify-end gap-2">

            <label className="text-sm text-gray-600">Desde</label>

            <input

              type="date"

              data-testid="dashboard-fecha-desde"

              value={desdeDraft}

              onChange={(e) => {

                const next = clampCustomDateRange(e.target.value);

                onDesdeDraftChange(next.desde, next.hasta);

              }}

              className="rounded border border-gray-300 text-sm p-1.5"

            />

            <label className="text-sm text-gray-600">Hasta</label>

            <input

              type="date"

              data-testid="dashboard-fecha-hasta"

              value={hastaDraft}

              onChange={(e) => {

                const next = clampCustomDateRange(desdeDraft, e.target.value);

                onHastaDraftChange(next.hasta);

              }}

              className="rounded border border-gray-300 text-sm p-1.5"

            />

            <button

              type="button"

              data-testid="dashboard-filtrar"

              onClick={onApplyCustomDates}

              disabled={!desdeDraft || !hastaDraft}

              className="rounded bg-blue-600 text-white text-sm px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"

            >

              Filtrar

            </button>

          </div>

        </div>

      )}

    </div>

  );

}


