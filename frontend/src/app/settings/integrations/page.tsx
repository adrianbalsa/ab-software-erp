"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  Loader2,
  Radio,
  Trash2,
} from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/AppShell";
import {
  createWebhookB2B,
  deleteWebhookB2B,
  listWebhooksB2B,
  revealWebhookSecret,
  testWebhookB2B,
  WEBHOOK_EVENT_TYPES,
  type WebhookB2BRow,
} from "@/lib/api";

function formatCreated(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 19);
    return d.toLocaleString("es-ES", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function IntegracionesContent() {
  const [rows, setRows] = useState<WebhookB2BRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [eventType, setEventType] = useState<string>(WEBHOOK_EVENT_TYPES[0]);
  const [targetUrl, setTargetUrl] = useState("");
  const [creating, setCreating] = useState(false);

  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [revealBusy, setRevealBusy] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState<string | null>(null);
  const [testBusy, setTestBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listWebhooksB2B();
      setRows(list);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar webhooks");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccess(null);
    setError(null);
    const url = targetUrl.trim();
    if (!url) {
      setError("Indica una URL HTTPS.");
      return;
    }
    setCreating(true);
    try {
      const created = await createWebhookB2B({
        event_type: eventType,
        target_url: url,
      });
      setTargetUrl("");
      setSuccess(
        `Webhook creado. Copia el secreto ahora; solo se muestra completo al crear o al revelar.`,
      );
      setRevealed((r) => ({ ...r, [created.id]: created.secret_key ?? "" }));
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo crear");
    } finally {
      setCreating(false);
    }
  };

  const onReveal = async (id: string) => {
    setRevealBusy(id);
    setError(null);
    try {
      const { secret_key } = await revealWebhookSecret(id);
      setRevealed((r) => ({ ...r, [id]: secret_key }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo revelar el secreto");
    } finally {
      setRevealBusy(null);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("¿Desactivar esta suscripción? El endpoint dejará de recibir eventos.")) {
      return;
    }
    setDeleteBusy(id);
    setError(null);
    try {
      await deleteWebhookB2B(id);
      setRevealed((r) => {
        const n = { ...r };
        delete n[id];
        return n;
      });
      setSuccess("Suscripción desactivada.");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo eliminar");
    } finally {
      setDeleteBusy(null);
    }
  };

  const onTest = async (id: string) => {
    setTestBusy(id);
    setError(null);
    setSuccess(null);
    try {
      await testWebhookB2B(id);
      setSuccess("Ping de prueba encolado. Revisa los logs del receptor o webhook_logs en el servidor.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo enviar el test");
    } finally {
      setTestBusy(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Integraciones (webhooks)
        </h1>
        <p className="mt-2 text-slate-600 text-sm max-w-2xl">
          Recibe notificaciones HTTPS firmadas (cabecera{" "}
          <code className="text-xs bg-slate-100 px-1 rounded">X-AB-Signature</code>) cuando
          ocurran eventos en tu empresa.
        </p>
      </div>

      {error && (
        <div
          className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div
          className="mb-4 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
          role="status"
        >
          <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{success}</span>
        </div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm mb-8">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Nueva suscripción</h2>
        <form onSubmit={onCreate} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="evt" className="block text-sm font-medium text-slate-700 mb-1">
                Tipo de evento
              </label>
              <select
                id="evt"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 bg-white focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                {WEBHOOK_EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="url" className="block text-sm font-medium text-slate-700 mb-1">
                URL de destino (HTTPS)
              </label>
              <input
                id="url"
                type="url"
                required
                placeholder="https://api.tu-sistema.com/webhooks/ab"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Añadir webhook
          </button>
        </form>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Suscripciones activas</h2>
          <button
            type="button"
            onClick={() => void load()}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Actualizar
          </button>
        </div>
        {loading ? (
          <div className="flex justify-center py-16 text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
        ) : rows.length === 0 ? (
          <p className="px-6 py-12 text-center text-slate-500 text-sm">
            No hay webhooks activos. Crea uno con el formulario superior.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-slate-600">
                  <th className="px-4 py-3 font-medium">Evento</th>
                  <th className="px-4 py-3 font-medium">URL</th>
                  <th className="px-4 py-3 font-medium">Alta</th>
                  <th className="px-4 py-3 font-medium text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((w) => (
                  <tr key={w.id} className="text-slate-800">
                    <td className="px-4 py-3 font-mono text-xs">{w.event_type}</td>
                    <td className="px-4 py-3 max-w-[min(28rem,40vw)] truncate" title={w.target_url}>
                      {w.target_url}
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {formatCreated(w.created_at ?? "")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {revealed[w.id] ? (
                          <code className="text-xs bg-slate-100 px-2 py-1 rounded max-w-[200px] truncate">
                            {revealed[w.id]}
                          </code>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void onReveal(w.id)}
                            disabled={revealBusy === w.id}
                            className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                          >
                            {revealBusy === w.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Eye className="w-3.5 h-3.5" />
                            )}
                            Revelar secreto
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => void onTest(w.id)}
                          disabled={testBusy === w.id}
                          className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                        >
                          {testBusy === w.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Radio className="w-3.5 h-3.5" />
                          )}
                          Enviar test
                        </button>
                        <button
                          type="button"
                          onClick={() => void onDelete(w.id)}
                          disabled={deleteBusy === w.id}
                          className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          {deleteBusy === w.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default function IntegracionesPage() {
  return (
    <AppShell active="integrations">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <div className="max-w-3xl mx-auto px-4 py-16 text-center text-slate-600">
            Solo el administrador de la empresa puede gestionar integraciones.
          </div>
        }
      >
        <IntegracionesContent />
      </RoleGuard>
    </AppShell>
  );
}
