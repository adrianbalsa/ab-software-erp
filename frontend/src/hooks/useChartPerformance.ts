"use client";

import { useEffect, useState } from "react";

import { useMediaQuery } from "@/hooks/useMediaQuery";

/**
 * Desactiva animaciones Recharts en dispositivos modestos, preferencia de usuario
 * o flag explícito `NEXT_PUBLIC_RECHARTS_STATIC=1`.
 */
export function useChartPerformance(): {
  staticCharts: boolean;
  isNarrow: boolean;
} {
  const prefersReducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const isNarrow = useMediaQuery("(max-width: 639px)");
  const [staticCharts, setStaticCharts] = useState(false);

  useEffect(() => {
    let shouldUseStaticCharts = false;
    if (process.env.NEXT_PUBLIC_RECHARTS_STATIC === "1") {
      shouldUseStaticCharts = true;
    } else if (prefersReducedMotion) {
      shouldUseStaticCharts = true;
    } else {
      const cores = navigator.hardwareConcurrency;
      const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
      shouldUseStaticCharts =
        (typeof cores === "number" && cores > 0 && cores <= 4) ||
        (typeof mem === "number" && mem > 0 && mem <= 4);
    }
    queueMicrotask(() => {
      setStaticCharts(shouldUseStaticCharts);
    });
  }, [prefersReducedMotion]);

  return { staticCharts, isNarrow };
}
