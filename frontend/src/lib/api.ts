import axios from "axios";
import { createBrowserClient } from "@supabase/ssr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.ablogistics-os.com";

// 1. Helpers de Auth (compatibilidad con legacy)
export const getAuthToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("sb-access-token") : null;
export const setAuthToken = (token: string) =>
  typeof window !== "undefined" && localStorage.setItem("sb-access-token", token);
export const clearAuthToken = () =>
  typeof window !== "undefined" && localStorage.removeItem("sb-access-token");
export const authHeaders = () => ({ Authorization: `Bearer ${getAuthToken()}` });

// 2. Instancia Principal
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// 3. Interceptor de Inyeccion JWT (El Bunker)
apiClient.interceptors.request.use(async (config) => {
  if (typeof window === "undefined") return config;

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

// 4. Exportaciones Multiples para evitar errores "Unknown"
export const api = apiClient; // Para componentes que usen import { api }
export { apiClient }; // Para componentes que usen import { apiClient }
export default apiClient; // Para componentes que usen import api from ...
