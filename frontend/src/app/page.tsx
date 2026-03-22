import type { Metadata } from "next";

import { LandingFAQ } from "@/components/landing/LandingFAQ";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { LandingHero } from "@/components/landing/LandingHero";
import { LandingHeroMotion } from "@/components/landing/LandingHeroMotion";
import { LandingHowItWorks } from "@/components/landing/LandingHowItWorks";
import { LandingMoats } from "@/components/landing/LandingMoats";
import { LandingPricing } from "@/components/landing/LandingPricing";
import { LandingROISimulator } from "@/components/landing/LandingROISimulator";

export const metadata: Metadata = {
  title: "AB Logistics OS | Sistema operativo para flotas inteligentes",
  description:
    "Margen por km, VeriFactu 2026, huella de carbono y EBITDA real. Dashboard unificado para transporte B2B.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-100">
      <LandingHeader />
      <main>
        <LandingHeroMotion>
          <LandingHero />
        </LandingHeroMotion>
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
