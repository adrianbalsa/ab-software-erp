import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Administración | AB Logistics OS",
  description: "Consola de administración global (empresas, usuarios, auditoría)",
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return children;
}
