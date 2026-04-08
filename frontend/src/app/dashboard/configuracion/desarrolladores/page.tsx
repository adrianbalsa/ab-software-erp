"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, Eye, EyeOff, Loader2, Plus, Trash2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  api,
  type WebhookEndpoint,
  type WebhookEventType,
} from "@/lib/api";

const EVENT_OPTIONS: { value: WebhookEventType; label: string }[] = [
  { value: "credit.limit_exceeded", label: "Límite de crédito superado" },
  { value: "verifactu.invoice_signed", label: "Factura VeriFactu firmada" },
  { value: "esg.certificate_generated", label: "Certificado ESG generado" },
];

function isHttpsUrl(raw: string): boolean {
  try {
    const u = new URL(raw.trim());
    return u.protocol === "https:";
  } catch {
    return false;
  }
}

function formatEventTypes(types: string[]): string {
  if (types.includes("*")) return "Todos (*)";
  return types
    .map((t) => EVENT_OPTIONS.find((o) => o.value === t)?.label ?? t)
    .join(", ");
}

export default function DesarrolladoresWebhooksPage() {
  const [rows, setRows] = useState<WebhookEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [subscribeAll, setSubscribeAll] = useState(false);
  const [selectedEvents, setSelectedEvents] = useState<Record<WebhookEventType, boolean>>({
    "credit.limit_exceeded": true,
    "verifactu.invoice_signed": false,
    "esg.certificate_generated": false,
  });
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [visibleId, setVisibleId] = useState<string | null>(null);
  const [secretLoading, setSecretLoading] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.webhooks.getEndpoints();
      setRows(list.filter((e) => e.is_active));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los endpoints.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setUrl("");
    setSubscribeAll(false);
    setSelectedEvents({
      "credit.limit_exceeded": true,
      "verifactu.invoice_signed": false,
      "esg.certificate_generated": false,
    });
    setCreateError(null);
  };

  const onCreate = async () => {
    setCreateError(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setCreateError("Introduce una URL.");
      return;
    }
    if (!isHttpsUrl(trimmed)) {
      setCreateError("La URL debe usar HTTPS.");
      return;
    }
    let event_types: WebhookEventType[] | ["*"];
    if (subscribeAll) {
      event_types = ["*"];
    } else {
      const picked = (Object.keys(selectedEvents) as WebhookEventType[]).filter(
        (k) => selectedEvents[k],
      );
      if (picked.length === 0) {
        setCreateError("Selecciona al menos un evento o «Suscribir a todos».");
        return;
      }
      event_types = picked;
    }

    setSaving(true);
    try {
      await api.webhooks.createEndpoint({ url: trimmed, event_types });
      setDialogOpen(false);
      resetForm();
      await load();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "No se pudo crear el endpoint.");
    } finally {
      setSaving(false);
    }
  };

  const toggleReveal = async (id: string) => {
    if (visibleId === id) {
      setVisibleId(null);
      return;
    }
    if (revealed[id]) {
      setVisibleId(id);
      return;
    }
    setSecretLoading(id);
    setError(null);
    try {
      const { secret_key } = await api.webhooks.getEndpointSecret(id);
      setRevealed((r) => ({ ...r, [id]: secret_key }));
      setVisibleId(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo obtener el secreto.");
    } finally {
      setSecretLoading(null);
    }
  };

  const copySecret = async (id: string) => {
    let text = revealed[id];
    if (!text) {
      try {
        const { secret_key } = await api.webhooks.getEndpointSecret(id);
        text = secret_key;
        setRevealed((r) => ({ ...r, [id]: secret_key }));
      } catch {
        setError("No se pudo obtener el secreto para copiar.");
        return;
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId(null), 2000);
    } catch {
      setError("No se pudo copiar al portapapeles.");
    }
  };

  const onDelete = async (id: string) => {
    if (!window.confirm("¿Desactivar este endpoint? Dejará de recibir eventos.")) return;
    setError(null);
    try {
      await api.webhooks.deleteEndpoint(id);
      setRevealed((r) => {
        const next = { ...r };
        delete next[id];
        return next;
      });
      if (visibleId === id) setVisibleId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo eliminar el endpoint.");
    }
  };

  return (
    <AppShell active="desarrolladores">
      <RoleGuard
        allowedRoles={["owner", "developer"]}
        fallback={
          <main className="p-8">
            <p className="text-sm text-zinc-600">
              Acceso restringido: la gestión de webhooks solo está disponible para owner o developer.
            </p>
          </main>
        }
      >
        <main className="p-6 lg:p-8 space-y-6 max-w-5xl">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-zinc-900">Panel de desarrolladores</h1>
              <p className="text-sm text-zinc-500 mt-1">
                Endpoints HTTPS con firma HMAC para eventos de tu espacio de trabajo.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                resetForm();
                setDialogOpen(true);
              }}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 shrink-0"
            >
              <Plus className="w-4 h-4" />
              Nuevo endpoint
            </button>
          </header>

          <Alert className="border-amber-200 bg-amber-50 text-amber-950">
            <AlertDescription>
              Utiliza el Secret Key para verificar las firmas HMAC SHA-256 en la cabecera{" "}
              <code className="rounded bg-amber-100/80 px-1.5 py-0.5 text-xs font-mono">
                X-ABLogistics-Signature
              </code>
              .
            </AlertDescription>
          </Alert>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {error}
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Endpoints activos</CardTitle>
              <CardDescription>
                URL de destino, eventos suscritos y estado. El secreto no se muestra hasta que lo
                solicites.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-zinc-500 py-8 justify-center">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Cargando…
                </div>
              ) : rows.length === 0 ? (
                <p className="text-sm text-zinc-500 py-6 text-center">
                  No hay endpoints activos. Crea uno con «Nuevo endpoint».
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>URL</TableHead>
                      <TableHead>Eventos suscritos</TableHead>
                      <TableHead>Estado</TableHead>
                      <TableHead className="w-[280px]">Secret</TableHead>
                      <TableHead className="w-[52px]" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell className="font-mono text-xs max-w-[200px] truncate">
                          {row.url}
                        </TableCell>
                        <TableCell className="text-sm text-zinc-700">
                          {formatEventTypes(row.event_types ?? [])}
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                            Activo
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-xs text-zinc-600 min-w-[7rem]">
                              {visibleId === row.id && revealed[row.id]
                                ? revealed[row.id]
                                : "••••••••"}
                            </span>
                            <button
                              type="button"
                              onClick={() => void toggleReveal(row.id)}
                              disabled={secretLoading === row.id}
                              className="rounded-md border border-zinc-200 p-1.5 text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                              title={visibleId === row.id ? "Ocultar" : "Mostrar secreto"}
                            >
                              {secretLoading === row.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : visibleId === row.id ? (
                                <EyeOff className="w-4 h-4" />
                              ) : (
                                <Eye className="w-4 h-4" />
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => void copySecret(row.id)}
                              className="rounded-md border border-zinc-200 p-1.5 text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
                              title="Copiar al portapapeles"
                            >
                              <Copy className="w-4 h-4" />
                            </button>
                            {copiedId === row.id ? (
                              <span className="text-xs text-emerald-600">Copiado</span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <button
                            type="button"
                            onClick={() => void onDelete(row.id)}
                            className="rounded-md p-1.5 text-rose-600 hover:bg-rose-50"
                            title="Desactivar endpoint"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Dialog
            open={dialogOpen}
            onOpenChange={(o) => {
              setDialogOpen(o);
              if (!o) resetForm();
            }}
          >
            <DialogContent aria-describedby="webhook-create-desc">
              <DialogHeader>
                <DialogTitle>Nuevo endpoint</DialogTitle>
                <DialogDescription id="webhook-create-desc">
                  Solo se aceptan URLs públicas con HTTPS. El secreto HMAC se genera al crear el
                  endpoint.
                </DialogDescription>
              </DialogHeader>
              <div className="px-6 space-y-4">
                <div>
                  <label htmlFor="wh-url" className="block text-sm font-medium text-zinc-700 mb-1">
                    URL del endpoint
                  </label>
                  <input
                    id="wh-url"
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://api.tudominio.com/webhooks/ab"
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                  />
                </div>
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <span className="text-sm font-medium text-zinc-700">Eventos</span>
                    <button
                      type="button"
                      onClick={() => setSubscribeAll((s) => !s)}
                      className={`text-xs font-medium rounded-lg px-2.5 py-1 border ${
                        subscribeAll
                          ? "border-blue-600 bg-blue-50 text-blue-800"
                          : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
                      }`}
                    >
                      Suscribir a todos (*)
                    </button>
                  </div>
                  <div className={`space-y-2 ${subscribeAll ? "opacity-40 pointer-events-none" : ""}`}>
                    {EVENT_OPTIONS.map((opt) => (
                      <label
                        key={opt.value}
                        className="flex items-center gap-2 text-sm text-zinc-800 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedEvents[opt.value]}
                          onChange={(e) =>
                            setSelectedEvents((s) => ({
                              ...s,
                              [opt.value]: e.target.checked,
                            }))
                          }
                          className="rounded border-zinc-300"
                        />
                        <span>{opt.label}</span>
                        <span className="text-xs text-zinc-400 font-mono">({opt.value})</span>
                      </label>
                    ))}
                  </div>
                </div>
                {createError && (
                  <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {createError}
                  </div>
                )}
              </div>
              <DialogFooter>
                <button
                  type="button"
                  onClick={() => setDialogOpen(false)}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void onCreate()}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Crear
                </button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
