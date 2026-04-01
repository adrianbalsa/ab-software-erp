"use client";

import type { SupabaseClient } from "@supabase/supabase-js";
import { getSupabaseClient } from "./api";

let _missingConfigLogged = false;

export function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return Boolean(url && anonKey);
}

export function getSupabaseBrowserClient(): SupabaseClient | null {
  const client = getSupabaseClient();
  if (!client) {
    if (!_missingConfigLogged) {
      console.error(
        "Faltan NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY. Se omite inicializacion de Supabase.",
      );
      _missingConfigLogged = true;
    }
    return null;
  }
  return client as SupabaseClient;
}

