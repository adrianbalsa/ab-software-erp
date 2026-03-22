/** URL pública del dashboard (Next.js app). */
export const APP_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_APP_URL) || "https://app.ablogistics-os.com";

/** CTA principal: entrada al flujo Google OAuth vía /auth/google en el frontend. */
export const START_NOW_URL = `${APP_URL.replace(/\/$/, "")}/auth/google`;

/** Login clásico (usuario/contraseña) por si OAuth no está disponible. */
export const LOGIN_URL = `${APP_URL.replace(/\/$/, "")}/login`;
