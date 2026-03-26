import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Portal cliente | AB Logistics OS",
  description: "Descarga de albaranes y facturas",
};

export default function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f8f9fc] text-zinc-900">{children}</div>
  );
}
