"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { API_BASE, authHeaders } from "@/lib/api";
import type {
  FinanceDashboard,
  FinanceMensualBar,
} from "@/hooks/useFinanceDashboard";

export type GastoApiRow = {
  id: string;
  categoria: string;
  total_chf: number;
  total_eur?: number | null;
  iva?: number | null;
};

export type FacturaApiRow = {
  id: number;
  cliente_id?: string;
  cliente?: string;
  base_imponible?: number;
  total_factura?: number;
  cuota_iva?: number;
  cliente_detalle?: { nombre?: string | null } | null;
};

/** kg CO₂ proxy: reparto del EBITDA por tasa de margen empresa sobre ingreso por cliente. */
export type ClienteMargenRow = {
  cliente: string;
  margen: number;
};

export type CostDistributionSlice = {
  name: string;
  value: number;
  fill: string;
};

const DONUT_PALETTE = [
  "#1e3a8a",
  "#1d4ed8",
  "#2563eb",
  "#3b82f6",
  "#475569",
  "#64748b",
  "#0f766e",
  "#059669",
];

function gastoNetoEUR(g: GastoApiRow): number {
  const gross =
    g.total_eur != null && g.total_eur > 0 ? g.total_eur : g.total_chf;
  const iva = g.iva;
  if (iva == null || iva <= 0) return Math.max(0, gross);
  return Math.max(0, gross - iva);
}

function ingresoNetoFactura(f: FacturaApiRow): number {
  if (f.base_imponible != null && !Number.isNaN(f.base_imponible)) {
    return Math.max(0, f.base_imponible);
  }
  const total = f.total_factura ?? 0;
  const cuota = f.cuota_iva ?? 0;
  return Math.max(0, total - cuota);
}

function clienteLabel(f: FacturaApiRow): string {
  const n = f.cliente_detalle?.nombre?.trim();
  if (n) return n.length > 28 ? `${n.slice(0, 26)}…` : n;
  const id = String(f.cliente_id ?? f.cliente ?? "?");
  return id.length > 12 ? `${id.slice(0, 10)}…` : id;
}

export type EconomicOverviewData = {
  dashboard: FinanceDashboard;
  /** Donut: gastos por categoría (Math Engine: neto sin IVA). */
  costDistribution: CostDistributionSlice[];
  /** Top 5 clientes por margen estimado (ingreso × EBITDA/ingresos). */
  topClientesMargen: ClienteMargenRow[];
  /** Serie mensual ya tipada para Area chart. */
  ingresosVsGastos: FinanceMensualBar[];
};

export function useEconomicOverview() {
  const [data, setData] = useState<EconomicOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = { ...authHeaders() };
      const [resDash, resGas, resFac] = await Promise.all([
        fetch(`${API_BASE}/finance/dashboard`, {
          credentials: "include",
          headers,
        }),
        fetch(`${API_BASE}/gastos/`, { credentials: "include", headers }),
        fetch(`${API_BASE}/facturas/`, { credentials: "include", headers }),
      ]);

      if (!resDash.ok) {
        const err = await resDash.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `Dashboard ${resDash.status}`,
        );
      }

      const dashboard = (await resDash.json()) as FinanceDashboard;

      let gastos: GastoApiRow[] = [];
      if (resGas.ok) {
        gastos = (await resGas.json()) as GastoApiRow[];
      }

      let facturas: FacturaApiRow[] = [];
      if (resFac.ok) {
        facturas = (await resFac.json()) as FacturaApiRow[];
      }

      const byCat = new Map<string, number>();
      for (const g of gastos) {
        const cat = (g.categoria || "Otros").trim() || "Otros";
        byCat.set(cat, (byCat.get(cat) ?? 0) + gastoNetoEUR(g));
      }
      const costDistribution: CostDistributionSlice[] = [...byCat.entries()]
        .filter(([, v]) => v > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([name, value], i) => ({
          name,
          value: Math.round(value * 100) / 100,
          fill: DONUT_PALETTE[i % DONUT_PALETTE.length],
        }));

      const ingresosTot = Math.max(0, dashboard.ingresos);
      const margenRate =
        ingresosTot > 0 ? dashboard.ebitda / ingresosTot : 0;

      const byCliente = new Map<string, { label: string; ingreso: number }>();
      for (const f of facturas) {
        const key = String(f.cliente_id ?? f.cliente ?? "unknown");
        const ing = ingresoNetoFactura(f);
        const prev = byCliente.get(key);
        const label = clienteLabel(f);
        if (prev) {
          byCliente.set(key, {
            label: prev.label,
            ingreso: prev.ingreso + ing,
          });
        } else {
          byCliente.set(key, { label, ingreso: ing });
        }
      }

      const topClientesMargen: ClienteMargenRow[] = [...byCliente.values()]
        .map(({ label, ingreso }) => ({
          cliente: label,
          margen: Math.round(ingreso * margenRate * 100) / 100,
        }))
        .sort((a, b) => b.margen - a.margen)
        .slice(0, 5);

      setData({
        dashboard,
        costDistribution,
        topClientesMargen,
        ingresosVsGastos: dashboard.ingresos_vs_gastos_mensual ?? [],
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar datos");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hasAreaData = useMemo(() => {
    if (!data?.ingresosVsGastos.length) return false;
    return data.ingresosVsGastos.some(
      (r) => r.ingresos > 0 || r.gastos > 0,
    );
  }, [data]);

  return {
    data,
    loading,
    error,
    refresh,
    hasAreaData,
  };
}
