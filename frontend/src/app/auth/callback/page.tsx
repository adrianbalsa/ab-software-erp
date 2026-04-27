"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { notifyJwtUpdated } from "@/lib/api";

const WELCOME_FLAG = "abl_oauth_welcome";

function AuthCallbackInner() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(WELCOME_FLAG, "1");
      notifyJwtUpdated();
    } catch {
      queueMicrotask(() => {
        setError("No se pudo preparar la sesión en este navegador.");
      });
      return;
    }
    router.replace("/onboarding");
  }, [router]);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#f4f6fb] px-6">
        <p className="max-w-md text-center text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={() => router.replace("/login")}
          className="mt-6 rounded-xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-800 shadow-sm hover:bg-zinc-50"
        >
          Ir al inicio de sesión
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#f4f6fb] px-6">
      <div
        className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-emerald-600"
        aria-hidden
      />
      <p className="text-sm font-medium text-zinc-600">Finalizando acceso…</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] text-sm text-zinc-500">
          Cargando…
        </div>
      }
    >
      <AuthCallbackInner />
    </Suspense>
  );
}
