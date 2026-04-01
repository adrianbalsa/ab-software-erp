import axios from "axios";
import { createBrowserClient } from "@supabase/ssr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.ablogistics-os.com";

// 1. Definicion de helpers para evitar errores de compilacion
export const getAuthToken = () =>
  typeof window !== "undefined" ? localStorage.getItem("sb-access-token") : null;
export const setAuthToken = (token: string) =>
  typeof window !== "undefined" && localStorage.setItem("sb-access-token", token);
export const clearAuthToken = () =>
  typeof window !== "undefined" && localStorage.removeItem("sb-access-token");

// 2. Instancia de Axios
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 3. Interceptor Maestro: Inyeccion dinamica del JWT de Supabase
apiClient.interceptors.request.use(
  async (config) => {
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
  },
  (error) => Promise.reject(error),
);

export default apiClient;
