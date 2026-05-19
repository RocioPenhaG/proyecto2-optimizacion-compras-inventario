import { useCallback, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export const RISK_TOOLTIP_TEXT = {
  Alto: "Producto sin stock disponible o con cobertura estimada de 7 días o menos. Requiere atención urgente o reposición pronta.",
  Medio: "Producto con stock igual o menor al mínimo configurado, o con cobertura estimada entre 8 y 15 días. Se recomienda monitorear.",
  Bajo: "Sin condición inmediata de desabastecimiento según cobertura y stock. Se recomienda sin acción inmediata.",
} as const;

export type RiskLevel = keyof typeof RISK_TOOLTIP_TEXT;

const RISK_BADGE_CLASS: Record<RiskLevel, string> = {
  Alto: "bg-red-100 text-red-800 border-red-200",
  Medio: "bg-amber-100 text-amber-800 border-amber-200",
  Bajo: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

const TOOLTIP_SURFACE_CLASS =
  "pointer-events-none max-w-[16rem] rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-xs leading-relaxed text-gray-100 shadow-lg";

function isRiskLevel(value: string): value is RiskLevel {
  return value === "Alto" || value === "Medio" || value === "Bajo";
}

interface RiskBadgeWithTooltipProps {
  level: string;
}

export function RiskBadgeWithTooltip({ level }: RiskBadgeWithTooltipProps) {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, placement: "below" as "above" | "below" });

  const hasTooltip = isRiskLevel(level);
  const badgeClass = hasTooltip ? RISK_BADGE_CLASS[level] : "bg-gray-100 text-gray-700 border-gray-200";

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
      aria-label={hasTooltip ? `${level}: más información` : undefined}
      data-testid={`risk-badge-${level.toLowerCase()}`}
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
      {level}
    </span>
  );

  const tooltip =
    hasTooltip && open
      ? createPortal(
          <div
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            data-testid={`risk-badge-tooltip-${level.toLowerCase()}`}
            style={{
              position: "fixed",
              top: coords.top,
              left: coords.left,
              transform: coords.placement === "above" ? "translate(-50%, -100%)" : "translateX(-50%)",
              zIndex: 9999,
            }}
            className={TOOLTIP_SURFACE_CLASS}
          >
            {RISK_TOOLTIP_TEXT[level]}
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
