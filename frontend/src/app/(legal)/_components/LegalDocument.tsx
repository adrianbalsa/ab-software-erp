import Link from "next/link";

type LegalDocumentProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

export function LegalDocument({ title, subtitle, children }: LegalDocumentProps) {
  return (
    <main className="min-h-screen overflow-x-clip bg-surface-base px-4 py-12 text-zinc-300 sm:px-6 sm:py-16">
      <div className="mx-auto w-full max-w-3xl rounded-2xl border border-zinc-800/90 bg-zinc-950/40 p-5 shadow-[0_0_0_1px_rgba(24,24,27,0.4)] backdrop-blur sm:p-10">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center rounded-full border border-zinc-700 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-zinc-300 transition hover:border-emerald-500/60 hover:text-emerald-300"
        >
          Volver al inicio
        </Link>

        <header className="mt-6 border-b border-zinc-800 pb-6">
          <h1 className="text-2xl font-extrabold text-zinc-100 sm:text-4xl">{title}</h1>
          <p className="mt-3 text-sm leading-relaxed text-zinc-400">{subtitle}</p>
        </header>

        <article className="prose prose-invert prose-zinc mt-8 max-w-none break-words text-[0.95rem] leading-7 prose-headings:scroll-mt-24 prose-headings:text-zinc-100 prose-h2:mt-10 prose-h2:border-b prose-h2:border-zinc-800 prose-h2:pb-2 prose-h3:mt-8 prose-a:break-all prose-a:text-emerald-400 prose-strong:text-zinc-100 sm:text-sm">
          {children}
        </article>
      </div>
    </main>
  );
}
