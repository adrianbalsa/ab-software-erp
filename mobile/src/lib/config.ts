import Constants from "expo-constants";

const stripTrailingSlash = (u: string) => u.replace(/\/$/, "");

export function getApiBaseUrl(): string {
  const fromEnv =
    process.env.EXPO_PUBLIC_API_BASE_URL?.trim() ||
    (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined)?.trim();

  if (fromEnv) return stripTrailingSlash(fromEnv);
  return "http://127.0.0.1:8000";
}

export function getSupabaseConfig(): { url: string; anonKey: string } | null {
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim();
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !anonKey) return null;
  return { url, anonKey };
}
