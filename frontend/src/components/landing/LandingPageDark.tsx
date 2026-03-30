"use client";

import { LandingFAQ } from "./LandingFAQ";
import { LandingFooter } from "./LandingFooter";
import { LandingHeader } from "./LandingHeader";
import { LandingHero } from "./LandingHero";
import { LandingHowItWorks } from "./LandingHowItWorks";
import { LandingMoats } from "./LandingMoats";
import { LandingPricing } from "./LandingPricing";
import { LandingROISimulator } from "./LandingROISimulator";

/** Landing original (tema oscuro) para el dominio de marketing. */
export function LandingPageDark() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <LandingHeader />
      <main>
        <LandingHero />
        <LandingROISimulator />
        <LandingMoats />
        <LandingHowItWorks />
        <LandingPricing />
        <LandingFAQ />
      </main>
      <LandingFooter />
    </div>
  );
}

