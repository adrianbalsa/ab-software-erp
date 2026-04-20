import type { Metadata } from "next";
import type { ReactNode } from "react";

import { PortalClienteAppShell } from "@/components/portal-cliente/PortalClienteAppShell";

export const metadata: Metadata = {
  title: "Portal del cliente | AB Logistics OS",
  description: "Autoservicio para cargadores: portes, facturas VeriFactu y certificación ESG.",
};

export default function PortalClienteRouteGroupLayout({ children }: { children: ReactNode }) {
  return <PortalClienteAppShell>{children}</PortalClienteAppShell>;
}
