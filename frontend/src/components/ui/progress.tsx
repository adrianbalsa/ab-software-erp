"use client";

import * as React from "react";

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export type ProgressProps = React.HTMLAttributes<HTMLDivElement> & {
  /** 0–100 */
  value: number;
  indicatorClassName?: string;
  indicatorStyle?: React.CSSProperties;
};

/**
 * Barra de progreso estilo shadcn (track + indicador).
 */
export function Progress({
  className,
  value,
  indicatorClassName,
  indicatorStyle,
  ...props
}: ProgressProps) {
  const v = Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(v)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={joinClasses(
        "relative w-full overflow-hidden rounded-full bg-zinc-200/80 dark:bg-zinc-800",
        className,
      )}
      {...props}
    >
      <div
        className={joinClasses("h-full rounded-full transition-[width] duration-300 ease-out", indicatorClassName)}
        style={{ width: `${v}%`, ...indicatorStyle }}
      />
    </div>
  );
}
