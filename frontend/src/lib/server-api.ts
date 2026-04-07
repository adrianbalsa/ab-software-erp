import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Session } from "@supabase/supabase-js";

import { jwtRbacRoleFromToken, type AppRbacRole } from "@/lib/api";

async function getServerSupabaseClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseAnonKey) return null;

  const cookieStore = await cookies();
  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // no-op in contexts where cookie writes are blocked
        }
      },
    },
  });
}

export async function getServerSession(): Promise<Session | null> {
  const supabase = await getServerSupabaseClient();
  if (!supabase) return null;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ?? null;
}

/** JWT de login FastAPI (`abl_auth_token`) o, si no hay, access_token de Supabase. */
export async function getSessionAccessTokenForRole(): Promise<string | null> {
  const cookieStore = await cookies();
  const abl = cookieStore.get("abl_auth_token")?.value ?? null;
  if (abl) return abl;
  const session = await getServerSession();
  return session?.access_token ?? null;
}

/** Rol para el primer paint SSR (cookie HttpOnly o sesión Supabase). */
export async function getServerInitialRole(): Promise<AppRbacRole | undefined> {
  const t = await getSessionAccessTokenForRole();
  if (!t) return undefined;
  return jwtRbacRoleFromToken(t);
}

export async function getServerAuthHeader(): Promise<Record<string, string>> {
  const token = await getSessionAccessTokenForRole();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
