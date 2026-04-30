import type { Dispatch, SetStateAction } from "react";

import { streamAdvisorAsk } from "@/lib/api";

/** Turno mínimo compartido por dashboard chat y Vampire Radar. */
export type AdvisorChatTurn = { role: "user" | "assistant"; content: string };

/**
 * ``POST /api/v1/advisor/ask`` (SSE o JSON) actualizando el último mensaje ``assistant`` vacío.
 * Asume que el caller ya añadió ``user`` + ``assistant`` con ``content: ""``.
 */
export async function streamAdvisorAskIntoMessages(
  body: { message: string; stream?: boolean; session_id?: string },
  ctx: {
    setMessages: Dispatch<SetStateAction<AdvisorChatTurn[]>>;
    onStreamError: (message: string) => void;
    onDone?: (model?: string | null, sessionId?: string | null) => void;
  },
): Promise<void> {
  const { setMessages, onStreamError, onDone } = ctx;
  await streamAdvisorAsk(body, {
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
      onStreamError(msg);
      setMessages((prev) => (prev.length < 2 ? prev : prev.slice(0, -2)));
    },
    onDone,
  });
}
