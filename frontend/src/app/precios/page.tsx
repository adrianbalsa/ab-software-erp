"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { getAuthToken } from "@/lib/api";
import { AbLogoMark } from "@/components/landing/AbLogoMark";

function PlanCard({
  name,
  price,
  perMonth,
  desc,
  bullets,
  planKey,
  cta,
  authed,
}: {
  name: string;
  price: string;
  perMonth: string;
  desc: string;
  bullets: string[];
  planKey: "starter" | "pro" | "enterprise";
  cta: string;
  authed: boolean;
}) {
  const href = authed ? `/payments/create-checkout?plan=${planKey}` : "/login";
  return (
    <article className="flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 shadow-lg shadow-black/20">
      <h2 className="text-lg font-semibold text-white">{name}</h2>
      <p className="mt-2 text-3xl font-bold tracking-tight text-emerald-400">
        {price}
        <span className="text-sm font-medium text-zinc-500"> {perMonth}</span>
      </p>
      <p className="mt-2 text-sm text-zinc-400">{desc}</p>
      <ul className="mt-4 flex-1 space-y-2 text-sm text-zinc-300">
        {bullets.map((b) => (
          <li key={b} className="flex gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" aria-hidden />
            <span>{b}</span>
          </li>
        ))}
      </ul>
      <Link
        href={href}
        className="mt-6 block rounded-xl bg-emerald-600 py-3 text-center text-sm font-semibold text-zinc-950 transition hover:bg-emerald-500"
      >
        {cta}
      </Link>
    </article>
  );
}

function PreciosContent() {
  const { catalog } = useOptionalLocaleCatalog();
  const p = catalog.pricing;
  const searchParams = useSearchParams();
  const cancelled = searchParams.get("checkout") === "cancel";
  const [authed] = useState(() => !!getAuthToken());

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-300">
      <header className="border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3 text-white">
            <AbLogoMark className="h-9 w-9 shrink-0" />
            <span className="text-base font-semibold tracking-tight">AB Logistics OS</span>
          </Link>
          <div className="flex items-center gap-3">
            <LocaleSwitcher />
            <Link
              href="/login"
              className="rounded-full border border-zinc-700 bg-zinc-900/50 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-300 transition hover:border-emerald-500/40 hover:text-white"
            >
              {p.loginCta}
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        {cancelled ? (
          <div
            className="mb-8 rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-sm text-amber-100"
            role="status"
          >
            {p.checkoutCancelled}
          </div>
        ) : null}

        <div className="max-w-2xl">
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">{p.title}</h1>
          <p className="mt-4 text-lg text-zinc-400">{p.subtitle}</p>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          <PlanCard
            name={p.starterName}
            price={p.starterPrice}
            perMonth={p.perMonth}
            desc={p.starterDesc}
            bullets={[...p.starterBullets]}
            planKey="starter"
            cta={p.choose}
            authed={authed}
          />
          <PlanCard
            name={p.proName}
            price={p.proPrice}
            perMonth={p.perMonth}
            desc={p.proDesc}
            bullets={[...p.proBullets]}
            planKey="pro"
            cta={p.choose}
            authed={authed}
          />
          <PlanCard
            name={p.entName}
            price={p.entPrice}
            perMonth={p.perMonth}
            desc={p.entDesc}
            bullets={[...p.entBullets]}
            planKey="enterprise"
            cta={p.choose}
            authed={authed}
          />
        </div>

        <p className="mt-10 max-w-2xl text-sm text-zinc-500">{p.currentNote}</p>
        <p className="mt-2 text-xs text-zinc-600">
          <Link href="/help/billing" className="text-emerald-500/90 hover:text-emerald-400">
            {catalog.nav.help}: Stripe
          </Link>
        </p>
      </main>
    </div>
  );
}

export default function PreciosPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-sm text-zinc-500">
          …
        </div>
      }
    >
      <PreciosContent />
    </Suspense>
  );
}
