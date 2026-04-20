import { createClient } from "@supabase/supabase-js";

import { getSupabaseConfig } from "./config";

let client: ReturnType<typeof createClient> | null = null;

export function getSupabaseClient() {
  if (client) return client;
  const cfg = getSupabaseConfig();
  if (!cfg) {
    throw new Error("Faltan EXPO_PUBLIC_SUPABASE_URL y EXPO_PUBLIC_SUPABASE_ANON_KEY");
  }
  client = createClient(cfg.url, cfg.anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}
