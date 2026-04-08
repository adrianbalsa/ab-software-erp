import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AppProviders } from "@/components/AppProviders";
import { SentryInit } from "@/components/SentryInit";
import { getServerInitialRole } from "@/lib/server-api";
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
  title: "AB Logistics OS",
  description: "Operaciones, finanzas, VeriFactu y sostenibilidad — AB Software",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const initialRole = await getServerInitialRole();

  return (
    <html lang="es">
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <SentryInit />
        <AppProviders initialRole={initialRole}>{children}</AppProviders>
      </body>
    </html>
  );
}
