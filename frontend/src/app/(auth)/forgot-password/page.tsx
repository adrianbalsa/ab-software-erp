"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { API_BASE, apiFetch, parseApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const { catalog } = useOptionalLocaleCatalog();
  const L = catalog.login;
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      toast.error(L.forgotPasswordEmailRequired);
      return;
    }
    setSubmitting(true);
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      if (!res.ok) {
        const msg = await parseApiError(res);
        throw new Error(msg);
      }
      setSent(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : L.forgotPasswordGenericError;
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center bg-[#0c0a09] px-4 py-12 text-stone-100">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.07]"
        style={{
          backgroundImage: `radial-gradient(circle at 20% 20%, #14b8a6 0%, transparent 45%),
            radial-gradient(circle at 80% 10%, #0d9488 0%, transparent 40%),
            radial-gradient(circle at 50% 80%, #115e59 0%, transparent 50%)`,
        }}
        aria-hidden
      />
      <div className="relative z-10 mb-4 flex w-full max-w-md justify-end">
        <LocaleSwitcher className="border-teal-500/30 bg-stone-900/80 text-stone-200" />
      </div>
      <Card className="relative z-10 w-full max-w-md border-teal-500/25 bg-stone-900/90 text-stone-100 shadow-[0_0_0_1px_rgba(20,184,166,0.08),0_24px_48px_rgba(0,0,0,0.45)] backdrop-blur-sm ring-teal-500/20">
        <CardHeader className="items-center text-center">
          <Image src="/logo.png" alt="AB Logistics OS" width={56} height={56} className="mb-2 h-14 w-14 object-contain" />
          <CardTitle className="text-xl font-semibold tracking-tight text-stone-50">
            {sent ? L.emailSentTitle : L.forgotPasswordTitle}
          </CardTitle>
          {!sent ? <CardDescription className="text-stone-400">{L.forgotPasswordSubtitle}</CardDescription> : null}
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="flex flex-col items-center gap-4 py-2 text-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-400" aria-hidden />
              <p className="text-sm leading-relaxed text-stone-300">{L.checkEmailInbox}</p>
            </div>
          ) : (
            <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
              <div className="space-y-1.5 text-left">
                <label htmlFor="forgot-email" className="text-sm font-medium text-stone-300">
                  {L.email}
                </label>
                <Input
                  id="forgot-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(ev) => setEmail(ev.target.value)}
                  className="h-10 border-teal-500/20 bg-stone-950/80 text-stone-100 placeholder:text-stone-500 focus-visible:border-teal-500/50 focus-visible:ring-teal-500/30"
                  disabled={submitting}
                />
              </div>
              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-gradient-to-br from-teal-600 to-emerald-700 font-semibold text-white hover:from-teal-500 hover:to-emerald-600"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    {L.pendingShort}
                  </>
                ) : (
                  L.sendInstructions
                )}
              </Button>
            </form>
          )}
        </CardContent>
        <CardFooter className="flex justify-center border-teal-500/15 bg-stone-950/40">
          <Link href="/login" className="text-sm text-teal-400/90 transition-colors hover:text-emerald-400">
            {L.forgotPasswordBackToLogin}
          </Link>
        </CardFooter>
      </Card>
    </main>
  );
}
