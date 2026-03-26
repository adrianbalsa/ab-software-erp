import { redirect } from "next/navigation";

/** Alias legacy: tesorería financiera vive en `/dashboard/finanzas/tesoreria`. */
export default function FinanzasTesoreriaRedirect() {
  redirect("/dashboard/finanzas/tesoreria");
}
