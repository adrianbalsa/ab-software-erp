import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SentryInit } from "@/components/SentryInit";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <SentryInit />
        {children}
      </body>
    </html>
  );
}
