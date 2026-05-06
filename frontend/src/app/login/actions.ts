"use server";

import { cookies } from "next/headers";

import { getAblAuthCookieSetOptions } from "@/lib/auth-cookie";
import { resolveApiBase } from "@/lib/api-base";
import { apiFetch } from "@/lib/api";
import { parseLoginApiFailure } from "@/lib/loginResponseErrors";

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
    res = await apiFetch(`${resolveApiBase().replace(/\/$/, "")}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
  } catch {
    return { error: "No se pudo contactar con el servidor." };
  }

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    const parsed = parseLoginApiFailure(res.status, payload);
    return { error: parsed.message, resetRequired: parsed.resetRequired };
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
