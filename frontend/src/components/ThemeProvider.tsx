"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

function migrateLegacyTheme(): void {
  if (typeof window === "undefined") return;
  try {
    if (localStorage.getItem("abl-theme")) return;
    const legacy = localStorage.getItem("abl-portal-theme");
    if (legacy === "light") localStorage.setItem("abl-theme", "light");
    else if (legacy === "dark") localStorage.setItem("abl-theme", "dark");
    if (legacy != null) localStorage.removeItem("abl-portal-theme");
  } catch {
    /* ignore */
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  migrateLegacyTheme();

  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem storageKey="abl-theme">
      {children}
    </NextThemesProvider>
  );
}
