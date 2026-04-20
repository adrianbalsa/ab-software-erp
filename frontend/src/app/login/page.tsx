"use client";

import Image from "next/image";
import { useActionState, useEffect, useState } from "react";
import { loginAction } from "./actions";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { notifyJwtUpdated } from "@/lib/api";
import { setAuthToken } from "@/lib/auth";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function LoginPage() {
  const { catalog } = useOptionalLocaleCatalog();
  const L = catalog.login;
  const [state, action, isPending] = useActionState(loginAction, null);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [oauthPending, setOauthPending] = useState(false);

  useEffect(() => {
    if (state && "success" in state && state.success) {
      setAuthToken(state.accessToken);
      notifyJwtUpdated();
      /* Navegación completa: garantiza que localStorage y la primera tanda de peticiones al API vean el JWT. */
      window.location.assign("/dashboard");
    }
  }, [state]);

  const onGoogleSignIn = async () => {
    setOauthError(null);
    setOauthPending(true);
    try {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        throw new Error(L.supabasePending);
      }
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/dashboard`,
        },
      });
      if (error) {
        throw error;
      }
    } catch (error) {
      setOauthError(error instanceof Error ? error.message : L.oauthFail);
    } finally {
      setOauthPending(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#f4f6fb] px-4 py-10">
      <div className="mb-4 flex w-full max-w-md justify-end">
        <LocaleSwitcher className="border-zinc-200 bg-white" />
      </div>
      <section className="w-full max-w-md rounded-2xl border border-zinc-200/90 bg-white p-8 shadow-[0_1px_3px_rgba(15,23,42,0.06)]">
        <div className="mb-6 flex flex-col items-center gap-4 text-center text-slate-800">
          <Image
            src="/logo.svg"
            alt="AB Logistics OS"
            width={64}
            height={64}
            className="rounded-xl object-contain"
            priority
          />
          <div>
            <h1 className="text-xl font-bold tracking-tight">AB Logistics OS</h1>
            <p className="text-sm text-slate-500">{L.tagline}</p>
          </div>
        </div>
        {state && "error" in state ? (
          <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {state.error}
          </p>
        ) : null}
        {oauthError ? (
          <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {oauthError}
          </p>
        ) : null}
        <form action={action} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-zinc-700">
              {L.email}
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              className="w-full rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-zinc-400 focus:ring-2 focus:ring-zinc-300"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-zinc-700">
              {L.password}
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className="w-full rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-zinc-400 focus:ring-2 focus:ring-zinc-300"
            />
          </div>
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex w-full items-center justify-center rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-zinc-800"
          >
            {isPending ? L.pendingShort : L.submitShort}
          </button>
        </form>
        <div className="relative py-3 text-center text-xs text-zinc-400">
          <span className="relative z-10 bg-white px-2">{L.oauthDivider}</span>
          <span className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-zinc-200" aria-hidden />
        </div>
        <button
          type="button"
          onClick={() => void onGoogleSignIn()}
          disabled={oauthPending}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white py-3 text-sm font-semibold text-zinc-800 shadow-sm transition-colors hover:border-emerald-300 hover:bg-emerald-50/80 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {oauthPending ? L.googlePending : L.google}
        </button>
      </section>
    </main>
  );
}
