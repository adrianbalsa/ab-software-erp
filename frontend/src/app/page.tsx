"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/components/auth/LoginForm";

/**
 * Entrada del subdominio app: solo acceso al sistema (sin marketing).
 * Sesión iniciada → cuadro de mando; si no, formulario de login.
 */
function HomeContent() {
  const router = useRouter();
  const [checked, setChecked] = useState(false);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    try {
      const t = localStorage.getItem("jwt_token");
      if (t) {
        setHasToken(true);
        router.replace("/dashboard");
      } else {
        setHasToken(false);
      }
    } catch {
      setHasToken(false);
    } finally {
      setChecked(true);
    }
  }, [router]);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] text-slate-500">
        Cargando…
      </div>
    );
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
