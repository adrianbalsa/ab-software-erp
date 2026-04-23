import { Suspense } from "react";

import { PricingCheckout } from "./PricingCheckout";

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <Suspense
        fallback={
          <div className="flex min-h-[50vh] items-center justify-center text-sm text-zinc-400">Cargando…</div>
        }
      >
        <PricingCheckout />
      </Suspense>
    </div>
  );
}
