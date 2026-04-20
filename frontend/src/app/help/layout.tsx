import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Help center — AB Logistics OS",
  description: "Commercial documentation, billing, security and compliance.",
};

export default function HelpLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-zinc-950">{children}</div>;
}
