"use client";

import { type ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

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
  void fetch("/api/auth/logout", { method: "POST" }).catch(() => {
    /* ignore */
  });
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
  const pathname = usePathname();

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      // FastAPI login solo rellena `abl_auth_token` + localStorage; Supabase suele quedar sin sesión.
      // `INITIAL_SESSION` con session=null NO es cierre de sesión: antes borrábamos todo y redirigíamos a /login.
      if (event !== "SIGNED_OUT") {
        return;
      }
      clearClientState();
      const shouldRedirect = pathname !== "/" && !pathname.startsWith("/auth");
      if (!shouldRedirect) return;
      router.replace("/login");
      router.refresh();
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [pathname, router]);

  return <>{children}</>;
}

