import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { getAblAuthCookieDeleteOptions } from "@/lib/auth-cookie";

export async function POST() {
  const cookieStore = await cookies();
  const del = getAblAuthCookieDeleteOptions();
  cookieStore.set("abl_auth_token", "", { ...del, maxAge: 0 });
  return NextResponse.json({ ok: true });
}
