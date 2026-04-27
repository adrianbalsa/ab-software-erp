"use server";

import { cookies } from "next/headers";

import { getAblAuthCookieSetOptions } from "@/lib/auth-cookie";
import { apiFetch } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://api.ablogistics-os.com";

export type LoginActionState =
  | { error: string; resetRequired?: boolean }
  | { success: true; accessToken: string }
  | null;

export async function loginAction(
  _prevState: LoginActionState,
  formData: FormData,
): Promise<LoginActionState> {
  void _prevState;
  const loginId = String(formData.get("email") ?? formData.get("username") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!loginId || !password) {
    return { error: "Introduce usuario/email y contraseña." };
  }

  const body = new URLSearchParams();
  body.set("username", loginId);
  body.set("password", password);

  let res: Response;
  try {
    res = await apiFetch(`${API_BASE.replace(/\/$/, "")}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
  } catch {
    return { error: "No se pudo contactar con el servidor." };
  }

  if (!res.ok) {
    let detail = "Credenciales incorrectas";
    let resetRequired = false;
    try {
      const err = (await res.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
      if (err?.detail && typeof err.detail === "object") {
        const payload = err.detail as { code?: unknown; message?: unknown };
        if (typeof payload.message === "string") detail = payload.message;
        resetRequired = payload.code === "password_reset_required";
      }
    } catch {
      /* ignore */
    }
    return { error: detail, resetRequired };
  }

  let accessToken: string;
  try {
    const data = (await res.json()) as { access_token?: string };
    if (!data?.access_token || typeof data.access_token !== "string") {
      return { error: "Respuesta de login inválida." };
    }
    accessToken = data.access_token;
  } catch {
    return { error: "Respuesta de login inválida." };
  }

  const cookieStore = await cookies();
  const opts = getAblAuthCookieSetOptions();
  cookieStore.set("abl_auth_token", accessToken, opts);

  return { success: true, accessToken };
}
