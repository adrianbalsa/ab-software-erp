"use client";

import { FadeInSection } from "./FadeInSection";
import { PricingPlansCheckout } from "./PricingPlansCheckout";

export function LandingPricing() {
  return (
    <FadeInSection
      id="pricing"
      className="scroll-mt-20 bg-surface-section px-4 py-24 sm:px-6 sm:py-28"
    >
      <PricingPlansCheckout variant="marketing-section" />
    </FadeInSection>
  );
}
