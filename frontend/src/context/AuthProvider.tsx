"use client";

import { type ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";

import { clearAuthToken } from "@/lib/auth";
import { getSupabaseBrowserClient } from "@/lib/supabase";

function clearBrowserCookies(): void {
  if (typeof document === "undefined") return;
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const raw of cookies) {
    const key = raw.split("=")[0]?.trim();
    if (!key) continue;
    document.cookie = `${key}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}

function clearClientState(): void {
  try {
    clearAuthToken();
  } catch {
    // ignore
  }
  try {
    window.localStorage.clear();
  } catch {
    // ignore
  }
  try {
    window.sessionStorage.clear();
  } catch {
    // ignore
  }
  clearBrowserCookies();
  try {
    window.dispatchEvent(new CustomEvent("abl:auth-invalidated"));
  } catch {
    // ignore
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      const invalid = event === "SIGNED_OUT" || !session;
      if (!invalid) return;
      clearClientState();
      router.replace("/login");
      router.refresh();
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  return <>{children}</>;
}

