/** Respuesta de `POST /auth/login` (`app/schemas/auth.py` → Token). */
export type LoginTokenResponse = {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
};
