import type { ReactNode } from "react";
import Link from "next/link";

type LegalShellProps = {
  title: string;
  lastUpdated?: string;
  children: ReactNode;
};

export function LegalShell({ title, lastUpdated, children }: LegalShellProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-6">
          <Link
            href="/"
            className="text-sm font-medium text-indigo-600 transition-colors hover:text-indigo-700"
          >
            ← AB Logistics OS
          </Link>
          <Link href="/legal" className="text-sm text-slate-600 transition-colors hover:text-slate-900">
            Marco legal
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10 pb-16">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
        {lastUpdated ? (
          <p className="mt-2 text-sm text-slate-500">Última actualización: {lastUpdated}</p>
        ) : null}
        <div className="mt-10 space-y-6 text-sm leading-relaxed text-slate-700 [&_h2]:mt-10 [&_h2]:scroll-mt-24 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-slate-900 [&_h3]:mt-6 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-slate-900 [&_ol]:list-decimal [&_ol]:space-y-2 [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5 [&_strong]:font-semibold [&_strong]:text-slate-900">
          {children}
        </div>
      </main>
    </div>
  );
}
