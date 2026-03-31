import { createMiddlewareClient } from "@supabase/auth-helpers-nextjs";
import { NextResponse, type NextRequest } from "next/server";

function isProtectedPath(pathname: string): boolean {
  const protectedPrefixes = [
    "/dashboard",
    "/admin",
    "/portal",
    "/finanzas",
    "/facturas",
    "/gastos",
    "/flota",
    "/clientes",
    "/portes",
    "/sostenibilidad",
    "/settings",
    "/perfil",
    "/bancos",
    "/payments",
  ];
  return protectedPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const res = NextResponse.next();

  if (pathname === "/login") {
    return res;
  }

  const supabase = createMiddlewareClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session && isProtectedPath(pathname)) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return res;
}

export const config = {
  matcher: [
    "/((?!login(?:/|$)|landing(?:/|$)|_next/static|_next/image|favicon.ico).*)",
  ],
};
