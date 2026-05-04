import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { DashboardBillingGate } from "@/components/dashboard/DashboardBillingGate";
import { getSessionAccessTokenForRole } from "@/lib/server-api";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const token = await getSessionAccessTokenForRole();
  if (!token) {
    redirect("/login");
  }

  return <DashboardBillingGate>{children}</DashboardBillingGate>;
}
