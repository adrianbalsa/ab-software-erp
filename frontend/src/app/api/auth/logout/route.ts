import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete("abl_auth_token");
  return NextResponse.json({ ok: true });
}
