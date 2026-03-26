"use client";

import type { ReactNode } from "react";

import { TourGuide } from "@/components/onboarding/TourGuide";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <TourGuide />
    </>
  );
}
