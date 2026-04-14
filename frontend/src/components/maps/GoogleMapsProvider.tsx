"use client";

import type { ReactNode } from "react";
import { APIProvider } from "@vis.gl/react-google-maps";

/** Prefer the public env name documented for Vercel / local `.env.local`. */
const apiKey =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ||
  process.env.NEXT_PUBLIC_MAPS_API_KEY ||
  "";

export function GoogleMapsProvider({ children }: { children: ReactNode }) {
  if (!apiKey) {
    return <>{children}</>;
  }
  return (
    <APIProvider apiKey={apiKey} libraries={["places", "routes"]}>
      {children}
    </APIProvider>
  );
}

export function mapsApiKeyAvailable(): boolean {
  return Boolean(apiKey);
}
