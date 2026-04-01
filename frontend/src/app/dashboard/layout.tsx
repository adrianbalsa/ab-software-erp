import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "@/lib/server-api";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const session = await getServerSession();
  if (!session) {
    redirect("/login");
  }

  return <>{children}</>;
}
