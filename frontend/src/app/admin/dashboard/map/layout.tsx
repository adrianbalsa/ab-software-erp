import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Mapa de actividad | Administración",
  description: "Densidad de portes y ticket medio de gastos por zona",
};

export default function AdminDashboardMapLayout({ children }: { children: ReactNode }) {
  return children;
}
