import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AB Logistics OS – ERP de Transporte y Logística en Galicia",
  description:
    "Software de gestión de transporte y logística en Galicia. ERP diseñado para proteger la rentabilidad de tu flota, automatizar la facturación y cumplir con VeriFactu 2026. Desarrollado en A Coruña.",
  keywords:
    "ERP logística, software transporte Galicia, VeriFactu, gestión flota, A Coruña",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="scroll-smooth light" data-theme="light" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        style={{ fontFamily: "var(--font-geist-sans), system-ui, sans-serif" }}
      >
        {children}
      </body>
    </html>
  );
}
