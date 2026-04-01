import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import type { Session } from "@supabase/supabase-js";

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

export async function getServerAuthHeader(): Promise<Record<string, string>> {
  const session = await getServerSession();
  if (!session?.access_token) return {};
  return { Authorization: `Bearer ${session.access_token}` };
}
