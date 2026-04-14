import { ShieldCheck, Clock, FileSearch, Ban } from "lucide-react";

export type OnboardingStatusProps = {
  riesgoAceptado?: boolean;
  mandatoActivo?: boolean;
  isBlocked?: boolean;
};

export function OnboardingStatusBadge({
  riesgoAceptado = false,
  mandatoActivo = false,
  isBlocked = false,
}: OnboardingStatusProps) {
  if (isBlocked) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/35 bg-red-950/50 px-2.5 py-1 text-xs font-semibold text-red-300">
        <Ban className="h-3.5 w-3.5" />
        Bloqueado
      </span>
    );
  }

  if (riesgoAceptado && mandatoActivo) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/35 bg-emerald-950/40 px-2.5 py-1 text-xs font-semibold text-emerald-400">
        <ShieldCheck className="h-3.5 w-3.5" />
        Activo
      </span>
    );
  }

  if (mandatoActivo && !riesgoAceptado) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-zinc-900/60 px-2.5 py-1 text-xs font-semibold text-emerald-500">
        <FileSearch className="h-3.5 w-3.5" />
        Riesgo en Estudio
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/35 bg-amber-950/40 px-2.5 py-1 text-xs font-semibold text-amber-300">
      <Clock className="h-3.5 w-3.5" />
      Pendiente
    </span>
  );
}
