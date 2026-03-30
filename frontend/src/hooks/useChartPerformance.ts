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
    if (process.env.NEXT_PUBLIC_RECHARTS_STATIC === "1") {
      setStaticCharts(true);
      return;
    }
    if (prefersReducedMotion) {
      setStaticCharts(true);
      return;
    }
    const cores = navigator.hardwareConcurrency;
    const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
    if (typeof cores === "number" && cores > 0 && cores <= 4) {
      setStaticCharts(true);
      return;
    }
    if (typeof mem === "number" && mem > 0 && mem <= 4) {
      setStaticCharts(true);
      return;
    }
    setStaticCharts(false);
  }, [prefersReducedMotion]);

  return { staticCharts, isNarrow };
}
