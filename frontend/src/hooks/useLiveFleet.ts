"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getLiveFleetTracking, type LiveFleetVehicle } from "@/lib/api";

const POLL_MS = 15_000;

export function useLiveFleet() {
  const [vehicles, setVehicles] = useState<LiveFleetVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getLiveFleetTracking();
      if (mounted.current) {
        setVehicles(data);
        setError(null);
      }
    } catch (e: unknown) {
      if (mounted.current) {
        setError(e instanceof Error ? e.message : "Error al cargar la flota");
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [refresh]);

  return { vehicles, loading, error, refresh };
}
