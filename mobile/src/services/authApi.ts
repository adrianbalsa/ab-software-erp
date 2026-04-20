import { apiFetchJson } from "../lib/api";
import type { LoginTokenResponse } from "../types/auth";

/**
 * OAuth2 password flow del backend: `application/x-www-form-urlencoded`.
 * Ver `app/api/routes/auth.py` → `OAuth2PasswordRequestForm`.
 */
export async function loginWithPassword(username: string, password: string): Promise<LoginTokenResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  body.set("grant_type", "password");

  return apiFetchJson<LoginTokenResponse>("/auth/login", {
    method: "POST",
    auth: false,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  });
}
