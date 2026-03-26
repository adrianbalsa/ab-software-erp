import { redirect } from "next/navigation";

/** Alias: tesorería vive en `/finanzas/tesoreria`. */
export default function DashboardTesoreriaRedirect() {
  redirect("/finanzas/tesoreria");
}
