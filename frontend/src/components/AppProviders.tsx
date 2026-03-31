"use client";

import type { ReactNode } from "react";

import { TourGuide } from "@/components/onboarding/TourGuide";
import { AuthProvider } from "@/context/AuthProvider";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      {children}
      <TourGuide />
    </AuthProvider>
  );
}
