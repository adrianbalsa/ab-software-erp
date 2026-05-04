import { describe, expect, it } from "vitest";

import { isAnonymousAuthEndpoint } from "@/lib/authAnonymousEndpoints";
import { parseLoginApiFailure } from "@/lib/loginResponseErrors";

describe("parseLoginApiFailure", () => {
  it("429 sin campo detail usa mensaje explícito de rate limit (no «Credenciales incorrectas»)", () => {
    const empty = parseLoginApiFailure(429, {});
    expect(empty.message).not.toContain("Credenciales incorrectas");
    expect(empty.message).toContain("Demasiadas solicitudes");

    const backendShape = parseLoginApiFailure(429, {
      code: "rate_limit_exceeded",
      error: "Rate limit exceeded",
      message: "Demasiadas solicitudes. Reintenta cuando finalice la ventana de rate limit.",
      retry_after: "42 seconds",
      request_id: "req-test-1",
    });
    expect(backendShape.message).toContain("Demasiadas solicitudes");
    expect(backendShape.message).toContain("(42 seconds)");
    expect(backendShape.message).toContain("Ref: req-test-1");
    expect(backendShape.resetRequired).toBe(false);
  });

  it("422 con detail lista FastAPI no cae en credenciales genéricas", () => {
    const r = parseLoginApiFailure(422, {
      detail: [{ type: "missing", loc: ["body", "username"], msg: "Field required" }],
      request_id: "rid-422",
    });
    expect(r.message).toContain("Field required");
    expect(r.message).toContain("Ref: rid-422");
    expect(r.resetRequired).toBe(false);
  });

  it("403 password_reset_required marca resetRequired", () => {
    const r = parseLoginApiFailure(403, {
      detail: {
        code: "password_reset_required",
        message: "Restablece tu contraseña.",
      },
    });
    expect(r.resetRequired).toBe(true);
    expect(r.message).toContain("Restablece");
  });

  it("401 conserva detail string del backend", () => {
    const r = parseLoginApiFailure(401, { detail: "Credenciales incorrectas" });
    expect(r.message).toBe("Credenciales incorrectas");
  });
});

describe("isAnonymousAuthEndpoint", () => {
  it("detecta login y refresh en URL absoluta o relativa", () => {
    expect(isAnonymousAuthEndpoint("https://api.example.com/auth/login")).toBe(true);
    expect(isAnonymousAuthEndpoint("https://api.example.com/auth/login?x=1")).toBe(true);
    expect(isAnonymousAuthEndpoint("/auth/refresh")).toBe(true);
    expect(isAnonymousAuthEndpoint("https://api.example.com/auth/me")).toBe(false);
  });
});
