import { useCallback, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export const HABITO_TOOLTIP_TEXT = {
  "Consumo creciente":
    "El consumo del producto muestra una tendencia ascendente durante el período analizado. Esto puede indicar un aumento sostenido en la demanda o uso del insumo.",
  "Consumo decreciente":
    "El consumo del producto presenta una tendencia descendente en el período analizado. Esto puede indicar una reducción progresiva en su utilización.",
  "Consumo estable":
    "El consumo del producto se mantiene relativamente constante durante el período analizado, sin variaciones significativas.",
  "Consumo frecuente":
    "El producto registra consumo en una parte importante de los días analizados, indicando un uso recurrente dentro de la operación.",
  "Consumo esporádico":
    "El producto presenta consumo ocasional o poco frecuente dentro del período analizado.",
  "Sin consumo reciente":
    "No se registraron movimientos de consumo del producto durante el período seleccionado.",
  "Bajo movimiento":
    "El producto tuvo solicitudes registradas, pero presentó poco o ningún consumo reciente durante el período analizado.",
} as const;

export type HabitoLevel = keyof typeof HABITO_TOOLTIP_TEXT;

const HABITO_BADGE_CLASS: Record<HabitoLevel, string> = {
  "Consumo creciente": "bg-violet-100 text-violet-800 border-violet-200",
  "Consumo decreciente": "bg-rose-100 text-rose-800 border-rose-200",
  "Consumo estable": "bg-sky-100 text-sky-800 border-sky-200",
  "Consumo frecuente": "bg-indigo-100 text-indigo-800 border-indigo-200",
  "Consumo esporádico": "bg-gray-100 text-gray-800 border-gray-200",
  "Sin consumo reciente": "bg-slate-100 text-slate-700 border-slate-200",
  "Bajo movimiento": "bg-slate-100 text-slate-700 border-slate-200",
};

const TOOLTIP_SURFACE_CLASS =
  "pointer-events-none max-w-[16rem] rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-xs leading-relaxed text-gray-100 shadow-lg";

function isHabitoLevel(value: string): value is HabitoLevel {
  return value in HABITO_TOOLTIP_TEXT;
}

function habitoTestSlug(habito: HabitoLevel): string {
  return habito
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, "-");
}

interface HabitoBadgeWithTooltipProps {
  habito: string;
}

export function HabitoBadgeWithTooltip({ habito }: HabitoBadgeWithTooltipProps) {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, placement: "below" as "above" | "below" });

  const hasTooltip = isHabitoLevel(habito);
  const badgeClass = hasTooltip ? HABITO_BADGE_CLASS[habito] : "bg-gray-100 text-gray-700 border-gray-200";
  const slug = hasTooltip ? habitoTestSlug(habito) : "otro";

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const tooltipHeight = tooltipRef.current?.offsetHeight ?? 72;
    const tooltipWidth = tooltipRef.current?.offsetWidth ?? 256;
    const margin = 8;
    const spaceBelow = window.innerHeight - rect.bottom - margin;
    const placeAbove = spaceBelow < tooltipHeight + 12;

    let left = rect.left + rect.width / 2;
    const halfWidth = tooltipWidth / 2;
    left = Math.max(halfWidth + margin, Math.min(window.innerWidth - halfWidth - margin, left));

    setCoords({
      top: placeAbove ? rect.top - margin : rect.bottom + margin,
      left,
      placement: placeAbove ? "above" : "below",
    });
  }, []);

  const show = useCallback(() => {
    if (!hasTooltip) return;
    setOpen(true);
  }, [hasTooltip]);

  const hide = useCallback(() => setOpen(false), []);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    const frame = requestAnimationFrame(() => updatePosition());
    const onScrollOrResize = () => updatePosition();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open, updatePosition]);

  const badge = (
    <span
      ref={triggerRef}
      tabIndex={hasTooltip ? 0 : undefined}
      role={hasTooltip ? "button" : undefined}
      aria-describedby={hasTooltip && open ? tooltipId : undefined}
      aria-label={hasTooltip ? `${habito}: más información` : undefined}
      data-testid={`habito-badge-${slug}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onKeyDown={(e) => {
        if (e.key === "Escape") hide();
      }}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        hasTooltip ? "cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-1" : ""
      } ${badgeClass}`}
    >
      {habito}
    </span>
  );

  const tooltip =
    hasTooltip && open
      ? createPortal(
          <div
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            data-testid={`habito-badge-tooltip-${slug}`}
            style={{
              position: "fixed",
              top: coords.top,
              left: coords.left,
              transform: coords.placement === "above" ? "translate(-50%, -100%)" : "translateX(-50%)",
              zIndex: 9999,
            }}
            className={TOOLTIP_SURFACE_CLASS}
          >
            {HABITO_TOOLTIP_TEXT[habito]}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      {badge}
      {tooltip}
    </>
  );
}
