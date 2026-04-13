"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Leaf,
  MessageCircle,
  Send,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { jwtPayload, streamAdvisorAsk } from "@/lib/api";

type ChatTurn = { role: "user" | "assistant"; content: string };

const QUICK_ACTIONS: { label: string; prompt: string }[] = [
  {
    label: "Resumen Demo",
    prompt:
      "Dame un resumen ejecutivo del entorno demo (flota, rutas, facturas, conciliación y margen EBITDA).",
  },
  {
    label: "Punto de equilibrio",
    prompt: "¿Cuál es mi punto de equilibrio hoy según mis datos?",
  },
  {
    label: "Huella CO₂",
    prompt: "¿Cómo puedo reducir mi huella de CO2 con mi flota y operación actuales?",
  },
  {
    label: "Margen por cliente",
    prompt: "Analiza mi margen por cliente y dime qué clientes aportan más rentabilidad.",
  },
];

const DEMO_EMPRESA_CODE = "DEMO-LOGISTICS-001";
const DEMO_EMPRESA_UUID = "406d68d7-52d8-5eb2-bff1-0a03095f7f6f";
const DEMO_PRELOAD = [
  "Sandbox cargado para demo:",
  "- Empresa: DEMO-LOGISTICS-001",
  "- Flota: 10 camiones (Euro III a Euro VI)",
  "- Rutas: 50 rutas validadas por Maps API",
  "- Facturación: 100 facturas encadenadas VeriFactu",
  "- Reconciliación: 10 cobros conciliados + 5 pendientes",
  "- EBITDA objetivo: margen operativo 15-20%",
].join("\n");

type InsightKind = "vampiro" | "verifactu" | "esg";

function classifyInsightParagraph(text: string): InsightKind | null {
  if (/ALERTA\s+VERIFACTU/i.test(text)) return "verifactu";
  if (/RIESGO\s+ESG/i.test(text)) return "esg";
  if (/VAMPIRO/i.test(text)) return "vampiro";
  return null;
}

/** Trocea por párrafos y envuelve bloques con palabras clave en tarjetas. */
function splitContentIntoSegments(
  content: string,
): Array<{ kind: "plain" | InsightKind; text: string }> {
  const parts = content.split(/\n\n+/);
  const out: Array<{ kind: "plain" | InsightKind; text: string }> = [];
  for (const raw of parts) {
    const text = raw.trim();
    if (!text) continue;
    const insight = classifyInsightParagraph(text);
    if (insight) out.push({ kind: insight, text });
    else out.push({ kind: "plain", text });
  }
  return out;
}

type QuickLinkRule = { test: (s: string) => boolean; label: string; href: string };

const QUICK_LINK_RULES: QuickLinkRule[] = [
  {
    test: (s) => /revis(ar|á)\s+(la\s+)?auditor[ií]a/i.test(s),
    label: "Ir a auditoría",
    href: "/dashboard/finanzas/auditoria",
  },
  {
    test: (s) => /revis(ar|á)\s+.*certificaci/i.test(s),
    label: "Certificaciones",
    href: "/dashboard/certificaciones",
  },
  {
    test: (s) => /auditor[ií]a(\s+de\s+facturas)?/i.test(s),
    label: "Auditoría",
    href: "/dashboard/finanzas/auditoria",
  },
  {
    test: (s) => /verifactu|cadena\s+de\s+hash|huella\s+de\s+registro/i.test(s),
    label: "Certificaciones",
    href: "/dashboard/certificaciones",
  },
  {
    test: (s) => /tesorer[ií]a|cobro\s+pendiente/i.test(s),
    label: "Tesorería",
    href: "/dashboard/finanzas/tesoreria",
  },
  {
    test: (s) => /\besg\b|huella\s+de\s+carbono|co[₂2]\s*\/\s*t/i.test(s),
    label: "ESG y certificaciones",
    href: "/dashboard/certificaciones",
  },
];

function resolveQuickLinks(content: string): { label: string; href: string }[] {
  const seen = new Set<string>();
  const out: { label: string; href: string }[] = [];
  for (const rule of QUICK_LINK_RULES) {
    if (rule.test(content) && !seen.has(rule.href)) {
      seen.add(rule.href);
      out.push({ label: rule.label, href: rule.href });
      if (out.length >= 4) break;
    }
  }
  return out;
}

function SmartInsightCard({ kind, children }: { kind: InsightKind; children: React.ReactNode }) {
  const shell =
    kind === "vampiro"
      ? "border-red-500/50 bg-red-500/10"
      : kind === "verifactu"
        ? "border-emerald-500/50 bg-emerald-500/10"
        : "border-amber-500/50 bg-amber-500/10";
  const Icon = kind === "vampiro" ? AlertTriangle : kind === "verifactu" ? ShieldAlert : Leaf;
  const title =
    kind === "vampiro" ? "Insight CIP" : kind === "verifactu" ? "Alerta VeriFactu" : "Riesgo ESG";

  return (
    <div
      className={`my-2 rounded-xl border px-3 py-2.5 ${shell}`}
      role="status"
      aria-label={title}
    >
      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-300">
        <Icon
          className={`h-4 w-4 shrink-0 ${
            kind === "vampiro" ? "text-red-400" : kind === "verifactu" ? "text-emerald-400" : "text-amber-400"
          }`}
          aria-hidden
        />
        {title}
      </div>
      <div className="text-[13px] leading-relaxed">{children}</div>
    </div>
  );
}

function MarkdownBlock({ content }: { content: string }) {
  return (
    <div className="logis-advisor-md-dark text-[13px] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 text-zinc-200">{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc pl-4 mb-2 space-y-0.5 text-zinc-200">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-4 mb-2 space-y-0.5 text-zinc-200">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-snug">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-zinc-50">{children}</strong>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 -mx-1">
              <table className="min-w-full text-xs border-collapse border border-zinc-600 rounded-md">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-zinc-800/90">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-zinc-600 px-2 py-1.5 text-left font-semibold text-zinc-100">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-zinc-600 px-2 py-1.5 align-top text-zinc-200">{children}</td>
          ),
          code: ({ className, children, ...props }) => {
            const inline = !className;
            if (inline) {
              return (
                <code className="rounded bg-zinc-800 px-1 text-[12px] text-emerald-400/90" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="block bg-zinc-900 rounded-md p-2 text-[12px] overflow-x-auto text-zinc-200 border border-zinc-700"
                {...props}
              >
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function AssistantContent({ content }: { content: string }) {
  const segments = splitContentIntoSegments(content);
  return (
    <>
      {segments.map((seg, i) =>
        seg.kind === "plain" ? (
          <MarkdownBlock key={`seg-${i}`} content={seg.text} />
        ) : (
          <SmartInsightCard key={`seg-${i}`} kind={seg.kind}>
            <MarkdownBlock content={seg.text} />
          </SmartInsightCard>
        ),
      )}
    </>
  );
}

function StreamingTypingIndicator() {
  return (
    <div className="flex items-center gap-2 px-1 py-1.5" aria-live="polite">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70 opacity-60" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.6)]" />
      </span>
      <span className="text-[11px] font-medium text-zinc-500">LogisAdvisor está escribiendo…</span>
    </div>
  );
}

function ResponseQuickLinks({ content }: { content: string }) {
  const links = resolveQuickLinks(content);
  if (links.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2 border-t border-zinc-800/80 pt-2">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className="inline-flex items-center rounded-lg border border-emerald-500/35 bg-emerald-950/40 px-2.5 py-1 text-[11px] font-medium text-emerald-300 transition-colors hover:border-emerald-400/60 hover:bg-emerald-900/50"
        >
          {l.label}
        </Link>
      ))}
    </div>
  );
}

export function LogisAdvisorChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const payload = jwtPayload();
  const empresaClaim = String(
    payload?.empresa_id ??
      payload?.empresaId ??
      payload?.tenant_id ??
      payload?.tenantId ??
      "",
  ).trim();
  const isDemoMode =
    empresaClaim === DEMO_EMPRESA_CODE ||
    empresaClaim === DEMO_EMPRESA_UUID ||
    (typeof window !== "undefined" && window.localStorage.getItem("ab.demo_mode") === "1");
  const [messages, setMessages] = useState<ChatTurn[]>(
    isDemoMode ? [{ role: "assistant", content: DEMO_PRELOAD }] : [],
  );
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    endRef.current?.scrollIntoView({ behavior });
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const threshold = 96;
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance < threshold;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    stickToBottomRef.current = true;
    requestAnimationFrame(() => scrollToBottom("auto"));
  }, [open, scrollToBottom]);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    scrollToBottom(streaming ? "auto" : "smooth");
  }, [messages, streaming, scrollToBottom]);

  async function runPrompt(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);
    setStreaming(true);
    stickToBottomRef.current = true;

    try {
      await streamAdvisorAsk(
        { message: trimmed, stream: true },
        {
          onDelta: (chunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { role: "assistant", content: last.content + chunk };
              }
              return next;
            });
          },
          onError: (msg) => {
            setError(msg);
            setMessages((prev) => (prev.length < 2 ? prev : prev.slice(0, -2)));
          },
        },
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al enviar el mensaje");
      setMessages((prev) => (prev.length >= 2 ? prev.slice(0, -2) : prev));
    } finally {
      setStreaming(false);
    }
  }

  function send() {
    void runPrompt(input);
    setInput("");
  }

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col items-end gap-3 pointer-events-none">
      {open && (
        <div
          id="logis-advisor-panel"
          className="pointer-events-auto w-[min(100vw-2rem,420px)] max-h-[min(72vh,560px)] flex flex-col rounded-2xl border border-zinc-600/80 bg-zinc-950 shadow-2xl shadow-black/50 overflow-hidden"
          role="dialog"
          aria-label="LogisAdvisor"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/90 bg-gradient-to-r from-zinc-900 via-zinc-950 to-black text-zinc-100">
            <div className="flex items-center gap-2.5">
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/15 p-2">
                <Bot className="h-5 w-5 text-emerald-500" aria-hidden />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight">LogisAdvisor</p>
                <p className="text-[11px] text-zinc-400 flex items-center gap-1">
                  <Sparkles className="h-3 w-3 text-emerald-500/90" />
                  Consultoría con tus datos financieros y ESG
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-2 rounded-lg hover:bg-zinc-800/80 transition-colors text-zinc-400 hover:text-zinc-200"
              aria-label="Cerrar chat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="px-3 pt-3 pb-2 flex flex-wrap gap-2 border-b border-zinc-800/90 bg-zinc-950/80">
              {QUICK_ACTIONS.map((a) => (
                <button
                  key={a.label}
                  type="button"
                  disabled={streaming}
                  onClick={() => void runPrompt(a.prompt)}
                  className="rounded-lg border border-zinc-700 bg-zinc-900/90 px-2.5 py-1.5 text-[11px] font-medium text-zinc-300 transition-colors hover:border-emerald-500/50 hover:text-emerald-400 disabled:opacity-40"
                >
                  {a.label}
                </button>
              ))}
            </div>

            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-zinc-950"
            >
              {messages.length === 0 && !streaming && (
                <p className="text-xs text-zinc-500 px-1 leading-relaxed">
                  Pregunta en lenguaje natural: equilibrio operativo, margen por km, huella de carbono o
                  rentabilidad por cliente. Los datos provienen de tu empresa (sesión actual).
                </p>
              )}
              {messages.map((m, i) => {
                const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
                const showTypingInBubble =
                  m.role === "assistant" && isLastAssistant && streaming && !m.content;
                const showTypingBelowBubble =
                  streaming &&
                  isLastAssistant &&
                  m.role === "assistant" &&
                  Boolean(m.content.length);
                return (
                  <React.Fragment key={`msg-${i}`}>
                    <div
                      className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm shadow-lg ${
                          m.role === "user"
                            ? "rounded-br-md bg-emerald-600 text-white"
                            : "bg-zinc-900/95 border border-zinc-700/80 text-zinc-100 rounded-bl-md"
                        }`}
                      >
                        {m.role === "assistant" ? (
                          showTypingInBubble ? (
                            <StreamingTypingIndicator />
                          ) : m.content ? (
                            <>
                              <AssistantContent content={m.content} />
                              {!streaming && isLastAssistant && (
                                <ResponseQuickLinks content={m.content} />
                              )}
                            </>
                          ) : null
                        ) : (
                          <p className="whitespace-pre-wrap break-words">{m.content}</p>
                        )}
                      </div>
                    </div>
                    {showTypingBelowBubble && (
                      <div className="flex justify-start pl-1">
                        <StreamingTypingIndicator />
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
              {error && (
                <div
                  className="rounded-lg px-3 py-2 text-xs border border-red-900/60 bg-red-950/50 text-red-200"
                  role="alert"
                >
                  {error}
                </div>
              )}
              <div ref={endRef} />
            </div>

            <div className="p-3 border-t border-zinc-800 bg-black/40 flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Escribe tu pregunta…"
                className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900/90 px-3 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-50"
                disabled={streaming}
                aria-label="Mensaje para LogisAdvisor"
              />
              <button
                type="button"
                onClick={() => send()}
                disabled={streaming || !input.trim()}
                className="shrink-0 rounded-xl border border-emerald-500/30 bg-emerald-600 p-2.5 text-white transition-colors hover:bg-emerald-500 disabled:opacity-40"
                aria-label="Enviar"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="pointer-events-auto flex items-center gap-2 rounded-full border border-zinc-600 bg-zinc-950 py-3 pl-4 pr-5 text-zinc-100 shadow-xl shadow-black/40 transition-colors hover:border-emerald-500/50 hover:bg-zinc-900"
        aria-expanded={open}
        aria-controls="logis-advisor-panel"
      >
        <MessageCircle className="h-5 w-5 text-emerald-500" />
        <span className="text-sm font-semibold">LogisAdvisor</span>
      </button>
    </div>
  );
}
