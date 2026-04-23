import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AB Logistics OS",
  description: "Planes, precios y contratación SaaS logística.",
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
