"use client";

import React, { useEffect, useRef, useState } from "react";
import { Bot, MessageCircle, Send, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { jwtEmpresaId, postAiChat, type AiChatMessage } from "@/lib/api";

type ChatTurn = AiChatMessage;

export function LogisAdvisorChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing, open]);

  async function send() {
    const text = input.trim();
    if (!text || typing) return;

    const history = messages.slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
    })) as AiChatMessage[];

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setTyping(true);

    try {
      const empresaId = jwtEmpresaId();
      const { reply } = await postAiChat({
        message: text,
        history,
        empresa_id: empresaId,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al enviar el mensaje");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setTyping(false);
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col items-end gap-3 pointer-events-none">
      {open && (
        <div
          id="logis-advisor-panel"
          className="pointer-events-auto w-[min(100vw-2rem,400px)] max-h-[min(70vh,520px)] flex flex-col rounded-2xl border border-slate-200/90 bg-white shadow-xl shadow-slate-900/10 overflow-hidden"
          role="dialog"
          aria-label="LogisAdvisor"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-gradient-to-r from-[#0b1224] to-slate-800 text-white">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-white/10">
                <Bot className="w-5 h-5" aria-hidden />
              </div>
              <div>
                <p className="text-sm font-semibold">LogisAdvisor</p>
                <p className="text-[11px] text-slate-300">Asistente IA · AB Logistics OS</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              aria-label="Cerrar chat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-slate-50/80">
              {messages.length === 0 && !typing && (
                <p className="text-xs text-slate-500 px-1">
                  Pregunta por KPIs financieros, facturas pendientes de cobro o eficiencia de flota.
                  Los datos se limitan a tu empresa (sesión actual).
                </p>
              )}
              {messages.map((m, i) => (
                <div
                  key={`${i}-${m.role}`}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm shadow-sm ${
                      m.role === "user"
                        ? "bg-[#2563eb] text-white rounded-br-md"
                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-md"
                    }`}
                  >
                    {m.role === "assistant" ? (
                      <MarkdownBlock content={m.content} />
                    ) : (
                      <p className="whitespace-pre-wrap break-words">{m.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {typing && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-md px-3 py-2 text-sm bg-white border border-slate-200 text-slate-500 italic">
                    Escribiendo…
                  </div>
                </div>
              )}
              {error && (
                <div className="ab-alert-error rounded-lg px-3 py-2 text-xs" role="alert">
                  {error}
                </div>
              )}
              <div ref={endRef} />
            </div>

            <div className="p-3 border-t border-slate-100 bg-white flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                placeholder="Escribe tu pregunta…"
                className="ab-input flex-1 text-sm"
                disabled={typing}
                aria-label="Mensaje para LogisAdvisor"
              />
              <button
                type="button"
                onClick={() => void send()}
                disabled={typing || !input.trim()}
                className="shrink-0 rounded-xl bg-[#2563eb] text-white p-2.5 hover:bg-[#1d4ed8] disabled:opacity-50 transition-colors"
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
        className="pointer-events-auto flex items-center gap-2 rounded-full bg-[#0b1224] text-white pl-4 pr-5 py-3 shadow-lg shadow-slate-900/25 hover:bg-slate-900 transition-colors"
        aria-expanded={open}
        aria-controls="logis-advisor-panel"
      >
        <MessageCircle className="w-5 h-5" />
        <span className="text-sm font-semibold">LogisAdvisor</span>
      </button>
    </div>
  );
}

function MarkdownBlock({ content }: { content: string }) {
  return (
    <div className="logis-advisor-md text-[13px] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-snug">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">{children}</strong>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 -mx-1">
              <table className="min-w-full text-xs border-collapse border border-slate-200 rounded-md">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-100">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-slate-200 px-2 py-1.5 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-200 px-2 py-1.5 align-top">{children}</td>
          ),
          code: ({ className, children, ...props }) => {
            const inline = !className;
            if (inline) {
              return (
                <code className="bg-slate-100 px-1 rounded text-[12px]" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className="block bg-slate-100 rounded-md p-2 text-[12px] overflow-x-auto" {...props}>
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
