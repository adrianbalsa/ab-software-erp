"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { fetchPortalMyRisk, jwtRbacRole, postPortalAcceptRisk, type PortalOnboardingMyRisk } from "@/lib/api";

type PortalClienteOnboardingContextValue = {
  loading: boolean;
  error: string | null;
  overview: PortalOnboardingMyRisk | null;
  refetch: () => Promise<void>;
  acceptRisk: () => Promise<void>;
  acceptLoading: boolean;
};

const PortalClienteOnboardingContext = createContext<PortalClienteOnboardingContextValue | null>(null);

export function PortalClienteOnboardingProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<PortalOnboardingMyRisk | null>(null);
  const [acceptLoading, setAcceptLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (jwtRbacRole() !== "cliente") {
      setLoading(false);
      setOverview(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPortalMyRisk();
      setOverview(data);
    } catch (e) {
      setOverview(null);
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const acceptRisk = useCallback(async () => {
    setAcceptLoading(true);
    setError(null);
    try {
      await postPortalAcceptRisk({});
      await refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setAcceptLoading(false);
    }
  }, [refetch]);

  const value = useMemo(
    () => ({
      loading,
      error,
      overview,
      refetch,
      acceptRisk,
      acceptLoading,
    }),
    [loading, error, overview, refetch, acceptRisk, acceptLoading],
  );

  return (
    <PortalClienteOnboardingContext.Provider value={value}>{children}</PortalClienteOnboardingContext.Provider>
  );
}

export function usePortalClienteOnboarding(): PortalClienteOnboardingContextValue {
  const ctx = useContext(PortalClienteOnboardingContext);
  if (!ctx) {
    throw new Error("usePortalClienteOnboarding debe usarse dentro de PortalClienteOnboardingProvider");
  }
  return ctx;
}
