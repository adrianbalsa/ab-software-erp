"use client";

import Link from "next/link";
import Image from "next/image";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronLeft } from "lucide-react";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { articleBySlug } from "@/help/articles";

export default function HelpArticlePage() {
  const params = useParams();
  const slug = typeof params.slug === "string" ? params.slug : "";
  const article = articleBySlug(slug);
  const { catalog, locale } = useOptionalLocaleCatalog();
  const h = catalog.helpHub;

  if (!article) {
    return (
      <div className="min-h-screen px-4 py-16 text-center text-zinc-400">
        <p className="text-lg text-white">404</p>
        <Link href="/help" className="mt-4 inline-block text-emerald-400 hover:text-emerald-300">
          {catalog.helpBilling.back}
        </Link>
      </div>
    );
  }

  const title = locale === "en" ? article.titles.en : article.titles.es;
  const body = locale === "en" ? article.body.en : article.body.es;

  return (
    <div className="min-h-screen text-zinc-300">
      <header className="border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3 text-white">
            <Image
              src="/logo.png"
              alt="AB Logistics logo"
              width={40}
              height={40}
              className="h-8 w-8 md:h-10 md:w-10 shrink-0 object-contain"
              priority
            />
            <span className="text-base font-semibold tracking-tight">AB Logistics OS</span>
          </Link>
          <LocaleSwitcher />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <Link
          href="/help"
          className="inline-flex items-center gap-1 text-sm font-medium text-emerald-500/90 hover:text-emerald-400"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden />
          {catalog.helpBilling.back}
        </Link>

        <p className="mt-4 text-[10px] font-bold uppercase tracking-widest text-emerald-500/90">
          {h.categories[article.category]}
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">{title}</h1>
        <p className="mt-2 text-xs text-zinc-500">
          {locale === "es" ? "Actualizado" : "Updated"} · {article.updated}
        </p>

        <article className="prose prose-invert prose-sm mt-8 max-w-none prose-headings:scroll-mt-20 prose-a:text-emerald-400 prose-strong:text-zinc-100">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
        </article>
      </main>
    </div>
  );
}
