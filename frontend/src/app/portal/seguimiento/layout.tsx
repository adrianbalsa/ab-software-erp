import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Seguimiento en mapa | Portal cliente",
  description: "Últimas entregas georreferenciadas del cargador",
};

export default function PortalSeguimientoLayout({ children }: { children: ReactNode }) {
  return children;
}
