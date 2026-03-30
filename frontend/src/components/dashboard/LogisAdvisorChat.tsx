"use client";

import React, { useEffect, useRef, useState } from "react";
import { Bot, MessageCircle, Send, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { jwtPayload, streamAdvisorChat, type AiChatMessage } from "@/lib/api";

type ChatTurn = AiChatMessage;

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
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming, open]);

  async function runPrompt(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const history = messages.slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
    })) as AiChatMessage[];

    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      await streamAdvisorChat(
        {
          message: trimmed,
          history,
        },
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
              <div className="p-2 rounded-xl bg-cyan-500/15 border border-cyan-500/30">
                <Bot className="w-5 h-5 text-cyan-400" aria-hidden />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight">LogisAdvisor</p>
                <p className="text-[11px] text-zinc-400 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-cyan-500/90" />
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
                  className="text-[11px] font-medium px-2.5 py-1.5 rounded-lg border border-zinc-700 bg-zinc-900/90 text-zinc-300 hover:border-cyan-600/60 hover:text-cyan-100 disabled:opacity-40 transition-colors"
                >
                  {a.label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-zinc-950">
              {messages.length === 0 && !streaming && (
                <p className="text-xs text-zinc-500 px-1 leading-relaxed">
                  Pregunta en lenguaje natural: equilibrio operativo, margen por km, huella de carbono o
                  rentabilidad por cliente. Los datos provienen de tu empresa (sesión actual).
                </p>
              )}
              {messages.map((m, i) => (
                <div
                  key={`msg-${i}`}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm shadow-lg ${
                      m.role === "user"
                        ? "bg-cyan-600 text-white rounded-br-md"
                        : "bg-zinc-900/95 border border-zinc-700/80 text-zinc-100 rounded-bl-md"
                    }`}
                  >
                    {m.role === "assistant" ? (
                      m.content ? (
                        <MarkdownBlock content={m.content} />
                      ) : streaming ? (
                        <span className="text-zinc-500 italic text-xs">Generando respuesta…</span>
                      ) : null
                    ) : (
                      <p className="whitespace-pre-wrap break-words">{m.content}</p>
                    )}
                  </div>
                </div>
              ))}
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
                className="flex-1 text-sm rounded-xl border border-zinc-700 bg-zinc-900/90 text-zinc-100 placeholder:text-zinc-600 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-cyan-600/40 disabled:opacity-50"
                disabled={streaming}
                aria-label="Mensaje para LogisAdvisor"
              />
              <button
                type="button"
                onClick={() => send()}
                disabled={streaming || !input.trim()}
                className="shrink-0 rounded-xl bg-cyan-600 text-white p-2.5 hover:bg-cyan-500 disabled:opacity-40 transition-colors border border-cyan-500/30"
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
        className="pointer-events-auto flex items-center gap-2 rounded-full bg-zinc-950 text-zinc-100 pl-4 pr-5 py-3 shadow-xl shadow-black/40 border border-zinc-600 hover:border-cyan-600/50 hover:bg-zinc-900 transition-colors"
        aria-expanded={open}
        aria-controls="logis-advisor-panel"
      >
        <MessageCircle className="w-5 h-5 text-cyan-400" />
        <span className="text-sm font-semibold">LogisAdvisor</span>
      </button>
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
                <code className="bg-zinc-800 px-1 rounded text-[12px] text-cyan-100/90" {...props}>
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
