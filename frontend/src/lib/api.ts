import axios from "axios";
import { createBrowserClient } from "@supabase/ssr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.ablogistics-os.com";

// 1. Instancia base
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// 2. Interceptor de Seguridad (Solo se activa en el cliente para evitar errores de build)
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

// 3. Exportaciones de compatibilidad total (Legacy + New)
export const api = apiClient;
export { apiClient };
export default apiClient;

// Helpers basicos
export const getAuthToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("sb-access-token") : null;
export const clearAuthToken = () =>
  typeof window !== "undefined" && localStorage.removeItem("sb-access-token");
