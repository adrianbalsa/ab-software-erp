export type AppRbacRole =
  | "owner"
  | "admin"
  | "traffic_manager"
  | "driver"
  | "cliente"
  | "developer";

const PUBLIC_PREFIXES = [
  "/",
  "/pricing",
  "/precios",
  "/help",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/auth/",
  "/legal",
  "/privacidad",
  "/terminos",
  "/aviso-legal",
  "/cookies",
  "/api/auth/",
];

const AUTH_REQUIRED_PREFIXES = [
  "/dashboard",
  "/facturas",
  "/gastos",
  "/flota",
  "/clientes",
  "/portes",
  "/finanzas",
  "/sostenibilidad",
  "/presupuestos",
  "/perfil",
  "/settings",
  "/bancos",
  "/operaciones",
  "/radar",
  "/payments",
  "/portal",
  "/portal-cliente",
  "/driver",
  "/admin",
];

const FINANCE_PREFIXES = [
  "/dashboard/finanzas",
  "/dashboard/settings/finance",
  "/finanzas",
  "/dashboard/tesoreria",
];

const OWNER_ONLY_PREFIXES = [
  "/dashboard/configuracion/desarrolladores",
  "/admin",
];

const CLIENTE_ONLY_PREFIXES = [
  "/portal-cliente",
  "/portal",
];

export function pathStartsWith(pathname: string, prefix: string): boolean {
  const normalizedPrefix =
    prefix === "/" ? "/" : prefix.endsWith("/") ? prefix.slice(0, -1) : prefix;
  if (normalizedPrefix === "/") return pathname === "/";
  return pathname === normalizedPrefix || pathname.startsWith(`${normalizedPrefix}/`);
}

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathStartsWith(pathname, prefix));
}

export function requiresAuth(pathname: string): boolean {
  return AUTH_REQUIRED_PREFIXES.some((prefix) => pathStartsWith(pathname, prefix));
}

export function coerceRole(raw: unknown): AppRbacRole | null {
  if (raw == null) return null;
  const s = String(raw).trim();
  if (!s) return null;
  const lower = s.toLowerCase();
  const valid: AppRbacRole[] = ["owner", "admin", "traffic_manager", "driver", "cliente", "developer"];
  if (valid.includes(lower as AppRbacRole)) return lower as AppRbacRole;

  const upper = s.toUpperCase();
  const legacy: Record<string, AppRbacRole> = {
    ADMIN: "owner",
    GESTOR: "traffic_manager",
    CONDUCTOR: "driver",
    TRAFFIC_MANAGER: "traffic_manager",
    DRIVER: "driver",
    CLIENTE: "cliente",
    DEVELOPER: "developer",
    OWNER: "owner",
  };
  return legacy[upper] ?? null;
}

export function roleFromJwtPayload(payload: Record<string, unknown> | null): AppRbacRole {
  if (!payload) return "driver";
  const appMetadata =
    payload.app_metadata && typeof payload.app_metadata === "object"
      ? (payload.app_metadata as Record<string, unknown>)
      : null;
  const userMetadata =
    payload.user_metadata && typeof payload.user_metadata === "object"
      ? (payload.user_metadata as Record<string, unknown>)
      : null;

  const candidates: unknown[] = [
    payload.rbac_role,
    payload.role,
    appMetadata?.rbac_role,
    appMetadata?.role,
    userMetadata?.rbac_role,
    userMetadata?.role,
  ];
  const appRoles = appMetadata?.roles;
  if (Array.isArray(appRoles)) candidates.push(...appRoles);
  if (typeof appRoles === "string") candidates.push(appRoles);

  for (const c of candidates) {
    const role = coerceRole(c);
    if (role) return role;
  }
  return "driver";
}

function isOwnerLike(role: AppRbacRole): boolean {
  return role === "owner" || role === "admin";
}

export function hasRoutePermission(pathname: string, role: AppRbacRole): boolean {
  if (CLIENTE_ONLY_PREFIXES.some((prefix) => pathStartsWith(pathname, prefix))) {
    return role === "cliente";
  }
  if (FINANCE_PREFIXES.some((prefix) => pathStartsWith(pathname, prefix))) {
    return isOwnerLike(role) || role === "developer";
  }
  if (OWNER_ONLY_PREFIXES.some((prefix) => pathStartsWith(pathname, prefix))) {
    return isOwnerLike(role) || role === "developer";
  }
  if (pathStartsWith(pathname, "/driver")) {
    return role === "driver" || role === "traffic_manager" || isOwnerLike(role) || role === "developer";
  }
  return role !== "cliente";
}
