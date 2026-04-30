"use client";

import { useQuery } from "@tanstack/react-query";

import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

export type FinancialHealthGranularity = "day" | "week" | "month";

export interface FinancialHealthSummary {
  ebitda: number;
  operating_margin_pct: number;
  cash_flow: number;
}

export interface FinancialHealthPoint {
  name: string;
  ingresos: number;
  gastos: number;
  co2_cost: number;
}

export interface FinancialHealthOut {
  summary: FinancialHealthSummary;
  series: FinancialHealthPoint[];
  meta: Record<string, unknown>;
}

export interface FinancialHealthFilters {
  start_date: string;
  end_date: string;
  granularity: FinancialHealthGranularity;
}

async function fetchFinancialHealth(filters: FinancialHealthFilters): Promise<FinancialHealthOut> {
  const params = new URLSearchParams({
    start_date: filters.start_date,
    end_date: filters.end_date,
    granularity: filters.granularity,
  });
  const res = await apiFetch(`${API_BASE}/api/v1/bi/financial-health?${params.toString()}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as FinancialHealthOut;
}

export function useFinancialHealth(filters: FinancialHealthFilters) {
  return useQuery({
    queryKey: ["bi", "financial-health", filters.start_date, filters.end_date, filters.granularity],
    queryFn: () => fetchFinancialHealth(filters),
    staleTime: 5 * 60 * 1000,
  });
}

