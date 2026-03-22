"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { writeBankOauthDone } from "@/lib/bankStorage";

/**
 * Tras el redirect de GoCardless OAuth: marca el flujo como completado y vuelve a ajustes financieros.
 */
export default function BancosCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    try {
      writeBankOauthDone();
    } catch {
      /* ignore */
    }
    router.replace("/dashboard/settings/finance");
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-zinc-50 text-zinc-700">
      <Loader2 className="h-10 w-10 animate-spin text-emerald-600" aria-hidden />
      <p className="text-sm font-medium">Completando conexión bancaria…</p>
    </div>
  );
}
