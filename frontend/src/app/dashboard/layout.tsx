import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getSessionAccessTokenForRole } from "@/lib/server-api";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const token = await getSessionAccessTokenForRole();
  if (!token) {
    redirect("/login");
  }

  return <>{children}</>;
}
