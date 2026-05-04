"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLocaleCatalog } from "@/context/LocaleContext";
import {
  fetchWorkspaceTeam,
  postAuthInviteUser,
  type WorkspaceTeamResponse,
} from "@/lib/api";
import { UserPlus } from "lucide-react";

export default function EquipoSettingsPage() {
  const { catalog } = useLocaleCatalog();
  const t = catalog.teamPage;
  const [data, setData] = useState<WorkspaceTeamResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "staff">("staff");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetchWorkspaceTeam();
      setData(res);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : t.loadError);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [t.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const atLimit =
    data != null &&
    data.limite_usuarios_equipo != null &&
    data.usuarios_equipo_actuales >= data.limite_usuarios_equipo;

  const onInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      toast.error(t.emailLabel);
      return;
    }
    setSubmitting(true);
    try {
      await postAuthInviteUser({ email: trimmed, role });
      toast.success(t.inviteSuccess);
      setEmail("");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t.inviteError);
    } finally {
      setSubmitting(false);
    }
  };

  const seatsLine =
    data?.limite_usuarios_equipo == null
      ? t.seatsUnlimited
      : `${data.usuarios_equipo_actuales} / ${data.limite_usuarios_equipo}`;

  const rbacLabel = (r: string) =>
    r === "owner" ? t.rbacOwner : r === "traffic_manager" ? t.rbacTraffic : r;

  return (
    <AppShell active="team">
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
        <header className="z-10 flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-4 border-b border-zinc-800 bg-zinc-950/90 px-6 py-4 backdrop-blur-md">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{t.title}</h1>
            <p className="mt-0.5 max-w-2xl text-sm text-zinc-400">{t.subtitle}</p>
          </div>
          <LocaleSwitcher />
        </header>

        <div className="max-w-2xl space-y-8 p-6 sm:p-8">
          {loading ? (
            <p className="text-sm text-zinc-500">…</p>
          ) : loadError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-950/20 p-4 text-sm text-rose-200">
              <p>{loadError}</p>
              <button
                type="button"
                onClick={() => void refresh()}
                className="mt-2 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
              >
                {t.retry}
              </button>
            </div>
          ) : data ? (
            <>
              <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
                <div className="flex items-center gap-2 text-zinc-200">
                  <UserPlus className="h-5 w-5 text-emerald-500" aria-hidden />
                  <h2 className="text-lg font-semibold">{t.seatsLabel}</h2>
                </div>
                <p className="mt-3 text-sm tabular-nums text-zinc-300">{seatsLine}</p>
                {atLimit ? (
                  <p className="mt-3 text-xs leading-relaxed text-amber-200/90">
                    {t.atLimitHint} {t.upgradeHint}
                  </p>
                ) : null}
              </section>

              <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h2 className="text-lg font-semibold text-zinc-100">{t.membersTitle}</h2>
                {data.members.length === 0 ? (
                  <p className="mt-3 text-sm text-zinc-500">{t.emptyMembers}</p>
                ) : (
                  <ul className="mt-4 divide-y divide-zinc-800/80">
                    {data.members.map((m) => (
                      <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                        <span className="truncate text-zinc-200" title={m.email}>
                          {m.email || "—"}
                        </span>
                        <span className="shrink-0 rounded-md border border-zinc-700/80 bg-zinc-950/60 px-2 py-0.5 text-xs text-zinc-400">
                          {rbacLabel(m.rbac_role)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h2 className="text-lg font-semibold text-zinc-100">{t.inviteCta}</h2>
                <form className="mt-4 space-y-4" onSubmit={(e) => void onInvite(e)}>
                  <div className="space-y-2">
                    <label htmlFor="invite-email" className="text-sm text-zinc-300">
                      {t.emailLabel}
                    </label>
                    <Input
                      id="invite-email"
                      type="email"
                      autoComplete="email"
                      placeholder={t.emailPlaceholder}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={atLimit || submitting}
                      className="border-zinc-700 bg-zinc-950 text-zinc-100"
                    />
                  </div>
                  <fieldset className="space-y-2">
                    <legend className="text-sm font-medium text-zinc-300">{t.roleLabel}</legend>
                    <label className="flex cursor-pointer gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 has-[:checked]:border-emerald-500/40">
                      <input
                        type="radio"
                        name="invite-role"
                        value="admin"
                        checked={role === "admin"}
                        onChange={() => setRole("admin")}
                        disabled={atLimit || submitting}
                        className="mt-1"
                      />
                      <span>
                        <span className="block text-sm font-medium text-zinc-200">{t.roleAdmin}</span>
                        <span className="mt-0.5 block text-xs text-zinc-500">{t.roleAdminHint}</span>
                      </span>
                    </label>
                    <label className="flex cursor-pointer gap-3 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 has-[:checked]:border-emerald-500/40">
                      <input
                        type="radio"
                        name="invite-role"
                        value="staff"
                        checked={role === "staff"}
                        onChange={() => setRole("staff")}
                        disabled={atLimit || submitting}
                        className="mt-1"
                      />
                      <span>
                        <span className="block text-sm font-medium text-zinc-200">{t.roleStaff}</span>
                        <span className="mt-0.5 block text-xs text-zinc-500">{t.roleStaffHint}</span>
                      </span>
                    </label>
                  </fieldset>
                  <Button
                    type="submit"
                    disabled={atLimit || submitting}
                    className="w-full bg-emerald-600 text-zinc-950 hover:bg-emerald-500"
                  >
                    {submitting ? t.inviting : t.inviteCta}
                  </Button>
                </form>
              </section>
            </>
          ) : null}
        </div>
      </main>
    </AppShell>
  );
}
