import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { hasRoutePermission, isPublicPath, requiresAuth, roleFromJwtPayload, type AppRbacRole } from "@/lib/route-authz";

const AUTH_COOKIE = "abl_auth_token";


function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length < 2) return null;
  const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  try {
    const json = atob(b64 + pad);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function redirectToLogin(req: NextRequest): NextResponse {
  const loginUrl = req.nextUrl.clone();
  loginUrl.pathname = "/login";
  const next = `${req.nextUrl.pathname}${req.nextUrl.search}`;
  loginUrl.searchParams.set("next", next);
  return NextResponse.redirect(loginUrl);
}

function redirectUnauthorized(req: NextRequest): NextResponse {
  const url = req.nextUrl.clone();
  url.pathname = "/dashboard";
  url.searchParams.set("forbidden", "1");
  return NextResponse.redirect(url);
}

function tokenFromSupabaseCookie(req: NextRequest): string | null {
  const candidate = req.cookies
    .getAll()
    .find((c) => c.name === "sb-access-token" || (c.name.startsWith("sb-") && c.name.endsWith("-auth-token")));
  if (!candidate?.value) return null;
  try {
    const parsed = JSON.parse(candidate.value) as { access_token?: unknown };
    if (typeof parsed.access_token === "string" && parsed.access_token.trim()) {
      return parsed.access_token.trim();
    }
  } catch {
    if (candidate.value.split(".").length >= 2) return candidate.value;
  }
  return null;
}

export async function proxy(req: NextRequest) {
  const pathname = req.nextUrl.pathname;
  let res = NextResponse.next({ request: { headers: req.headers } });

  const token = req.cookies.get(AUTH_COOKIE)?.value ?? tokenFromSupabaseCookie(req) ?? null;
  const payload = token ? decodeJwtPayload(token) : null;
  const role = roleFromJwtPayload(payload);

  if (!token && requiresAuth(pathname) && !isPublicPath(pathname)) {
    return redirectToLogin(req);
  }
  if (token && pathStartsWith(pathname, "/login")) {
    const dest = role === "cliente" ? "/portal-cliente" : "/dashboard";
    const target = req.nextUrl.clone();
    target.pathname = dest;
    target.search = "";
    return NextResponse.redirect(target);
  }
  if (token && requiresAuth(pathname) && !hasRoutePermission(pathname, role)) {
    return redirectUnauthorized(req);
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    return res;
  }

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return req.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => req.cookies.set(name, value));
        res = NextResponse.next({ request: { headers: req.headers } });
        cookiesToSet.forEach(({ name, value, options }) => res.cookies.set(name, value, options));
      },
    },
  });

  await supabase.auth.getSession();

  return res;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|icon\\.svg|logo\\.svg|apple-icon\\.svg).*)",
  ],
};
