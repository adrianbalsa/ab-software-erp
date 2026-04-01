import axios from "axios";
import { createBrowserClient } from "@supabase/ssr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.ablogistics-os.com";

// 1. Helpers universales (para evitar fallos de importacion)
export const getAuthToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("sb-access-token") : null;
export const setAuthToken = (token: string) =>
  typeof window !== "undefined" && localStorage.setItem("sb-access-token", token);
export const clearAuthToken = () =>
  typeof window !== "undefined" && localStorage.removeItem("sb-access-token");
export const authHeaders = () => ({ Authorization: `Bearer ${getAuthToken()}` });

// 2. Instancia de Axios con interceptor de seguridad
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
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
  }
  return config;
});

// 3. Exportaciones por nombre y por defecto (Compatibilidad Total)
export const api = apiClient;
export { apiClient };
export default apiClient;
