"use client";

import { LandingBentoGrid } from "./LandingBentoGrid";
import { LandingFAQ } from "./LandingFAQ";
import { LandingFooter } from "./LandingFooter";
import { LandingMarketingHero } from "./LandingMarketingHero";
import { LandingMarketingNav } from "./LandingMarketingNav";
import { LandingPricing } from "./LandingPricing";
import { LandingTechSpecsBar } from "./LandingTechSpecsBar";

/** Landing pública (tema oscuro, bento + hero) para el dominio de marketing. */
export function LandingPageDark() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-400">
      <LandingMarketingNav />
      <main>
        <LandingMarketingHero />
        <LandingBentoGrid />
        <LandingPricing />
        <LandingFAQ />
        <LandingTechSpecsBar />
      </main>
      <LandingFooter />
    </div>
  );
}
