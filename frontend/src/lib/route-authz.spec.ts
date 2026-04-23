import { describe, expect, it } from "vitest";

import {
  hasRoutePermission,
  isPublicPath,
  requiresAuth,
  roleFromJwtPayload,
  type AppRbacRole,
} from "@/lib/route-authz";

describe("route-authz", () => {
  describe("public/auth route classification", () => {
    it("marks legal and login pages as public", () => {
      expect(isPublicPath("/login")).toBe(true);
      expect(isPublicPath("/legal")).toBe(true);
      expect(isPublicPath("/auth/reset-password")).toBe(true);
    });

    it("requires auth on dashboard and app routes", () => {
      expect(requiresAuth("/dashboard")).toBe(true);
      expect(requiresAuth("/dashboard/finanzas")).toBe(true);
      expect(requiresAuth("/portal-cliente")).toBe(true);
    });
  });

  describe("jwt role normalization", () => {
    it("uses explicit rbac_role when available", () => {
      expect(roleFromJwtPayload({ rbac_role: "owner" })).toBe("owner");
      expect(roleFromJwtPayload({ rbac_role: "GESTOR" })).toBe("traffic_manager");
    });

    it("falls back to app_metadata roles array", () => {
      const payload = {
        app_metadata: {
          roles: ["CLIENTE"],
        },
      };
      expect(roleFromJwtPayload(payload)).toBe("cliente");
    });

    it("defaults to driver when payload has no recognized role", () => {
      expect(roleFromJwtPayload({})).toBe("driver");
      expect(roleFromJwtPayload(null)).toBe("driver");
    });
  });

  describe("permission matrix by route", () => {
    const roles: AppRbacRole[] = ["owner", "admin", "traffic_manager", "driver", "cliente", "developer"];

    it("allows finance routes only to owner/admin/developer", () => {
      const path = "/dashboard/finanzas";
      const allowed = new Set(["owner", "admin", "developer"]);
      for (const role of roles) {
        expect(hasRoutePermission(path, role)).toBe(allowed.has(role));
      }
    });

    it("allows admin routes only to owner/admin/developer", () => {
      const path = "/admin";
      const allowed = new Set(["owner", "admin", "developer"]);
      for (const role of roles) {
        expect(hasRoutePermission(path, role)).toBe(allowed.has(role));
      }
    });

    it("allows portal cliente routes only to cliente", () => {
      const path = "/portal-cliente/sostenibilidad";
      for (const role of roles) {
        expect(hasRoutePermission(path, role)).toBe(role === "cliente");
      }
    });

    it("allows driver route to operational roles except cliente", () => {
      const path = "/driver/portes/1/entrega";
      const allowed = new Set(["driver", "traffic_manager", "owner", "admin", "developer"]);
      for (const role of roles) {
        expect(hasRoutePermission(path, role)).toBe(allowed.has(role));
      }
    });
  });
});
