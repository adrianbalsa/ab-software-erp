"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { FleetEfficiencyTable, TruckEfficiency } from "@/components/dashboard/FleetEfficiencyTable";
import { TruckProfitChart } from "@/components/dashboard/TruckProfitChart";
import { AppShell } from "@/components/AppShell";
import { API_BASE, apiFetch } from "@/lib/api";
import { EfficiencyRankingSchema } from "@/lib/schemas";

export default function EficienciaFlotaPage() {
  const [data, setData] = useState<TruckEfficiency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiFetch<TruckEfficiency[]>(
        `${API_BASE}/api/v1/fleet/efficiency-ranking`,
        undefined,
        EfficiencyRankingSchema,
      );
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los datos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return (
    <AppShell active="eficiencia">
      <div className="flex-1 space-y-6 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Eficiencia de Flota</h2>
        </div>

        {loading ? (
          <div className="flex h-[400px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="rounded-md bg-destructive/15 p-4 text-destructive">{error}</div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
            <div className="col-span-full lg:col-span-4">
              <h3 className="mb-4 text-lg font-medium">Ranking de Eficiencia</h3>
              <FleetEfficiencyTable data={data} />
            </div>
            <div className="col-span-full lg:col-span-3">
              <h3 className="mb-4 text-lg font-medium">Métricas Financieras</h3>
              <TruckProfitChart data={data} />
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
