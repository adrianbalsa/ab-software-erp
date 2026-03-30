"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/components/auth/LoginForm";
import { LandingPageDark } from "@/components/landing/LandingPageDark";
import { getAuthToken } from "@/lib/auth";

function isMarketingRootHostname(hostname: string): boolean {
  const h = hostname.toLowerCase();
  return h === "ablogistics-os.com" || h === "www.ablogistics-os.com";
}

/**
 * Raíz del ERP:
 * - `ablogistics-os.com` / `www.*` → landing pública (visitante sin contexto de app).
 * - Cualquier otro host (p. ej. `app.ablogistics-os.com`, localhost) → sin JWT muestra Login;
 *   con JWT redirige a `/dashboard`.
 */
function HomeContent() {
  const router = useRouter();
  const [phase, setPhase] = useState<"loading" | "marketing" | "app">("loading");
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    const hostname = typeof window !== "undefined" ? window.location.hostname : "";
    if (isMarketingRootHostname(hostname)) {
      setPhase("marketing");
      return;
    }

    try {
      const t = getAuthToken();
      if (t) {
        setHasToken(true);
        router.replace("/dashboard");
      } else {
        setHasToken(false);
      }
    } catch {
      setHasToken(false);
    } finally {
      setPhase("app");
    }
  }, [router]);

  if (phase === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] text-slate-500">
        Cargando…
      </div>
    );
  }

  if (phase === "marketing") {
    return <LandingPageDark />;
  }

  if (hasToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] text-slate-500">
        Redirigiendo…
      </div>
    );
  }

  return <LoginForm hideBackToMarketing />;
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] text-slate-500">
          Cargando…
        </div>
      }
    >
      <HomeContent />
    </Suspense>
  );
}
