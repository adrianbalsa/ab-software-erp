import type { Metadata } from "next";
import { Geist_Mono, Plus_Jakarta_Sans } from "next/font/google";
import { AppProviders } from "@/components/AppProviders";
import { getServerInitialRole } from "@/lib/server-api";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AB Logistics OS",
  description: "Operaciones, finanzas, VeriFactu y sostenibilidad — AB Software",
  icons: {
    icon: [
      { url: "/logo.png", type: "image/png", sizes: "32x32" },
      { url: "/logo.png", type: "image/png", sizes: "192x192" },
    ],
    shortcut: [{ url: "/logo.png", type: "image/png", sizes: "32x32" }],
    apple: [{ url: "/logo.png", type: "image/png", sizes: "180x180" }],
  },
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
        className={`${plusJakartaSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <AppProviders initialRole={initialRole}>{children}</AppProviders>
      </body>
    </html>
  );
}
