"use client";

import { Suspense } from "react";
import { LandingBentoGrid } from "./LandingBentoGrid";
import { LandingFAQ } from "./LandingFAQ";
import { LandingFooter } from "./LandingFooter";
import { LandingHowItWorks } from "./LandingHowItWorks";
import { LandingMarketingHero } from "./LandingMarketingHero";
import { LandingMarketingNav } from "./LandingMarketingNav";
import { LandingPricing } from "./LandingPricing";
import { LandingSocialProof } from "./LandingSocialProof";
import { LandingTechSpecsBar } from "./LandingTechSpecsBar";
import { LandingTrustStrip } from "./LandingTrustStrip";

/**
 * Landing pública (marketing): una historia comercial continua — producto,
 * prueba social, cumplimiento VeriFactu, funnel self-serve, pricing único
 * alineado con Stripe y catálogo de planes.
 */
export function LandingPageDark() {
  return (
    <div className="min-h-screen overflow-x-clip bg-surface-base text-zinc-300">
      <LandingMarketingNav />
      <main>
        <LandingMarketingHero />
        <LandingSocialProof />
        <LandingBentoGrid />
        <LandingTrustStrip />
        <LandingHowItWorks />
        <Suspense fallback={null}>
          <LandingPricing />
        </Suspense>
        <LandingFAQ />
        <LandingTechSpecsBar />
      </main>
      <LandingFooter />
    </div>
  );
}
