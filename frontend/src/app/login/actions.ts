"use server";

import { cookies } from "next/headers";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://api.ablogistics-os.com";

export type LoginActionState =
  | { error: string }
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
    res = await fetch(`${API_BASE.replace(/\/$/, "")}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
  } catch {
    return { error: "No se pudo contactar con el servidor." };
  }

  if (!res.ok) {
    let detail = "Credenciales incorrectas";
    try {
      const err = (await res.json()) as { detail?: unknown };
      if (typeof err?.detail === "string") detail = err.detail;
    } catch {
      /* ignore */
    }
    return { error: detail };
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
  const isProd = process.env.NODE_ENV === "production";
  cookieStore.set("abl_auth_token", accessToken, {
    path: "/",
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7,
  });

  return { success: true, accessToken };
}
