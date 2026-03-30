"use client";

import { useState } from "react";
import { MessageCircle, X, Send, TrendingUp, Leaf, Route } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

type QuickAction = {
  id: string;
  label: string;
  icon: React.ReactNode;
  query: string;
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "ebitda",
    label: "Calculate my current EBITDA",
    icon: <TrendingUp className="h-4 w-4" />,
    query: "¿Cuál es mi EBITDA actual y cómo se compara con el mes anterior?",
  },
  {
    id: "co2",
    label: "Show CO2 efficiency",
    icon: <Leaf className="h-4 w-4" />,
    query: "¿Cuál es mi huella de carbono este mes y cómo puedo reducirla?",
  },
  {
    id: "routes",
    label: "Route recommendations",
    icon: <Route className="h-4 w-4" />,
    query: "¿Qué rutas puedo optimizar para reducir costes y emisiones?",
  },
];

export function LogisAdvisor() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/v1/chatbot/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ message: text.trim() }),
      });

      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }

      const data = await response.json();

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response || "No se pudo generar una respuesta.",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content:
          "Lo siento, ocurrió un error al procesar tu solicitud. Verifica tu conexión e intenta de nuevo.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAction = (query: string) => {
    sendMessage(query);
  };

  return (
    <>
      {!isOpen && (
        <Button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 h-14 w-14 rounded-full bg-emerald-600 p-0 shadow-2xl shadow-emerald-900/60 transition-all hover:scale-110 hover:bg-emerald-500"
          aria-label="Abrir LogisAdvisor"
        >
          <MessageCircle className="h-6 w-6 text-white" />
        </Button>
      )}

      {isOpen && (
        <Card className="fixed bottom-6 right-6 z-50 flex h-[600px] w-[420px] flex-col overflow-hidden border border-zinc-800 bg-zinc-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-zinc-800 bg-gradient-to-r from-emerald-950 to-zinc-950 px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-600">
                <MessageCircle className="h-5 w-5 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-100">LogisAdvisor</h3>
                <p className="text-xs text-zinc-400">Asistente de logística IA</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsOpen(false)}
              className="h-8 w-8 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {messages.length === 0 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-8 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-950/60 border border-emerald-800/40">
                <MessageCircle className="h-8 w-8 text-emerald-500" />
              </div>
              <div>
                <h4 className="text-base font-semibold text-zinc-200">¡Hola! Soy LogisAdvisor</h4>
                <p className="mt-1 text-sm text-zinc-400">
                  Puedo ayudarte con insights financieros, eficiencia de rutas y sostenibilidad.
                </p>
              </div>
              <div className="mt-4 flex w-full flex-col gap-2">
                {QUICK_ACTIONS.map((action) => (
                  <Button
                    key={action.id}
                    variant="outline"
                    size="sm"
                    onClick={() => handleQuickAction(action.query)}
                    className="w-full justify-start gap-2 border-zinc-800 bg-zinc-900/60 text-left text-xs text-zinc-200 hover:bg-emerald-950/60 hover:border-emerald-800/60 hover:text-emerald-100"
                    disabled={isLoading}
                  >
                    {action.icon}
                    <span>{action.label}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.length > 0 && (
            <ScrollArea className="flex-1 px-4 py-4">
              <div className="space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex flex-col gap-1",
                      msg.role === "user" ? "items-end" : "items-start",
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                        msg.role === "user"
                          ? "bg-emerald-600 text-white"
                          : "border border-zinc-800 bg-zinc-900 text-zinc-100",
                      )}
                    >
                      {msg.content}
                    </div>
                    <span className="text-[10px] text-zinc-500">
                      {msg.timestamp.toLocaleTimeString("es-ES", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex items-start gap-2">
                    <div className="max-w-[85%] rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-400">
                      <div className="flex items-center gap-2">
                        <div className="flex gap-1">
                          <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                          <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-500 delay-75" />
                          <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-500 delay-150" />
                        </div>
                        <span>LogisAdvisor está pensando...</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          )}

          <div className="border-t border-zinc-800 bg-zinc-950 p-4">
            {messages.length > 0 && (
              <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
                {QUICK_ACTIONS.map((action) => (
                  <Button
                    key={action.id}
                    variant="outline"
                    size="sm"
                    onClick={() => handleQuickAction(action.query)}
                    className="shrink-0 gap-1.5 border-zinc-800 bg-zinc-900/60 text-xs text-zinc-300 hover:bg-emerald-950/60 hover:border-emerald-800/60 hover:text-emerald-100"
                    disabled={isLoading}
                  >
                    {action.icon}
                    {action.label}
                  </Button>
                ))}
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              className="flex gap-2"
            >
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Escribe tu pregunta..."
                disabled={isLoading}
                className="flex-1 border-zinc-800 bg-zinc-900 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-emerald-600"
              />
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isLoading}
                className="bg-emerald-600 hover:bg-emerald-500"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </Card>
      )}
    </>
  );
}
