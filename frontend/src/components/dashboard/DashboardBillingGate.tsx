"use client";

import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { isOwnerLike, type AppRbacRole } from "@/lib/api";
import { useRole } from "@/hooks/useRole";
import { fetchEmpresaQuotaGate, type EmpresaQuotaGate } from "@/lib/postAuthNavigation";
import { normalizePlanQueryParam } from "@/lib/productPlans";

function adminCanPay(role: AppRbacRole): boolean {
  return isOwnerLike(role) || role === "developer";
}

async function fetchQuotaGate(): Promise<EmpresaQuotaGate | null> {
  return fetchEmpresaQuotaGate();
}

function DashboardBillingGateInner({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { role } = useRole();
  const [splash, setSplash] = useState(true);

  const applyRedirects = useCallback(async () => {
    const q = await fetchQuotaGate();
    if (!q) {
      return;
    }
    const must = Boolean(q.must_complete_checkout);
    const susp = Boolean(q.billing_suspended);
    const billingPath = "/dashboard/settings/billing";
    const pendingPath = "/dashboard/billing-pending";
    const admin = adminCanPay(role);

    if (susp && !pathname.startsWith(billingPath)) {
      router.replace(billingPath);
      return;
    }
    if (must && admin && !pathname.startsWith(billingPath)) {
      const planSlug = normalizePlanQueryParam(q.plan_type ?? "starter");
      router.replace(`/payments/create-checkout?plan=${encodeURIComponent(planSlug)}&source=resume`);
      return;
    }
    if (must && !admin && pathname !== pendingPath && !pathname.startsWith(billingPath)) {
      router.replace(pendingPath);
      return;
    }
  }, [pathname, role, router]);

  useEffect(() => {
    let cancelled = false;
    const failSafe = globalThis.setTimeout(() => {
      if (!cancelled) setSplash(false);
    }, 11000);
    void (async () => {
      await applyRedirects();
      globalThis.clearTimeout(failSafe);
      if (!cancelled) setSplash(false);
    })();
    return () => {
      cancelled = true;
      globalThis.clearTimeout(failSafe);
    };
  }, [applyRedirects]);

  useEffect(() => {
    if (searchParams.get("checkout") !== "success") return;
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      void (async () => {
        const q = await fetchQuotaGate();
        if (q && !q.must_complete_checkout) {
          window.clearInterval(id);
          try {
            window.dispatchEvent(new CustomEvent("abl:checkout-activated"));
          } catch {
            /* ignore */
          }
          router.replace("/dashboard");
          return;
        }
        if (n >= 20) window.clearInterval(id);
      })();
    }, 2000);
    return () => window.clearInterval(id);
  }, [searchParams, router]);

  if (splash) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 dark:bg-zinc-950 px-6 text-center">
        <div
          className="h-9 w-9 animate-spin rounded-full border-2 border-zinc-600 border-t-emerald-500"
          aria-hidden
        />
        <div className="max-w-sm space-y-2">
          <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Preparando tu espacio de trabajo</p>
          <p className="text-xs leading-relaxed text-zinc-500">
            Comprobamos tu suscripción. Si tarda más de unos segundos tras pagar en Stripe, espera un momento
            o abre Facturación.
          </p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/dashboard/settings/billing")}
          className="text-xs font-medium text-emerald-500/90 underline-offset-4 hover:text-emerald-400 hover:underline"
        >
          Ir a facturación
        </button>
      </div>
    );
  }

  return <>{children}</>;
}

export function DashboardBillingGate({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 px-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">Cargando…</p>
        </div>
      }
    >
      <DashboardBillingGateInner>{children}</DashboardBillingGateInner>
    </Suspense>
  );
}
