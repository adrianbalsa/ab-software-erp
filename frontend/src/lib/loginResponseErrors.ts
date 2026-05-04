/**
 * Interpretación estable de errores HTTP de POST /auth/login para la UI.
 * Evita mostrar «Credenciales incorrectas» ante 429, 422 u otros cuerpos sin detail string.
 */

export type ParsedLoginError = {
  message: string;
  resetRequired: boolean;
};

function requestIdSuffix(payload: Record<string, unknown>): string {
  const rid = payload.request_id;
  if (typeof rid === "string" && rid.trim()) return ` (Ref: ${rid.trim()})`;
  return "";
}

function formatValidationDetail(detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const m = (item as { msg?: unknown }).msg;
          return typeof m === "string" ? m : "";
        }
        return "";
      })
      .filter(Boolean);
    return parts.length > 0 ? parts.join("; ") : "Formato de solicitud incorrecto.";
  }
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      return "Formato de solicitud incorrecto.";
    }
  }
  return "Formato de solicitud incorrecto.";
}

/** Interpreta el cuerpo JSON de error del backend (o null si no hubo JSON). */
export function parseLoginApiFailure(status: number, payload: unknown): ParsedLoginError {
  const obj =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : {};
  const rid = requestIdSuffix(obj);

  if (status === 429) {
    const msg =
      typeof obj.message === "string" && obj.message.trim()
        ? obj.message.trim()
        : "Demasiadas solicitudes de inicio de sesión desde esta red. Espera un minuto e inténtalo de nuevo.";
    const retry = typeof obj.retry_after === "string" && obj.retry_after.trim() ? obj.retry_after.trim() : "";
    const body = retry ? `${msg} (${retry})` : msg;
    return { message: `${body}${rid}`, resetRequired: false };
  }

  if (status === 403) {
    const detail = obj.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const d = detail as Record<string, unknown>;
      if (d.code === "password_reset_required") {
        const m =
          typeof d.message === "string" && d.message.trim()
            ? d.message.trim()
            : "Por seguridad debes restablecer tu contraseña antes de iniciar sesión.";
        return { message: `${m}${rid}`, resetRequired: true };
      }
      if (typeof d.message === "string" && d.message.trim()) {
        return { message: `${d.message.trim()}${rid}`, resetRequired: false };
      }
    }
    if (typeof detail === "string" && detail.trim()) {
      return { message: `${detail.trim()}${rid}`, resetRequired: false };
    }
    const fallback =
      typeof obj.message === "string" && obj.message.trim() ? obj.message.trim() : "Acceso denegado.";
    return { message: `${fallback}${rid}`, resetRequired: false };
  }

  if (status === 422) {
    return { message: `${formatValidationDetail(obj.detail)}${rid}`, resetRequired: false };
  }

  if (status === 401) {
    const msg =
      typeof obj.detail === "string" && obj.detail.trim()
        ? obj.detail.trim()
        : "Credenciales incorrectas";
    return { message: `${msg}${rid}`, resetRequired: false };
  }

  if (status >= 500) {
    return {
      message: `El servidor no está disponible temporalmente. Inténtalo más tarde.${rid}`,
      resetRequired: false,
    };
  }

  let msg = "No se pudo iniciar sesión.";
  if (typeof obj.detail === "string" && obj.detail.trim()) msg = obj.detail.trim();
  else if (typeof obj.message === "string" && obj.message.trim()) msg = obj.message.trim();
  return { message: `${msg}${rid}`, resetRequired: false };
}
