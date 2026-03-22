import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de privacidad (RGPD) | AB Logistics OS",
};

export default function PrivacidadPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 px-6 py-16 max-w-2xl mx-auto">
      <Link href="/" className="text-sm text-blue-400 hover:underline">
        ← Volver al inicio
      </Link>
      <h1 className="mt-8 text-2xl font-bold text-white">Política de privacidad (RGPD)</h1>
      <p className="mt-4 text-zinc-400 text-sm leading-relaxed">
        Información sobre tratamiento de datos personales en preparación. Puede ejercer sus derechos
        ARCO contactando a{" "}
        <a href="mailto:comercial@ablogistics.os" className="text-emerald-400 hover:underline">
          comercial@ablogistics.os
        </a>
        .
      </p>
    </div>
  );
}
