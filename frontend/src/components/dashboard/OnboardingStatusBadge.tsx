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
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
        <Ban className="h-3.5 w-3.5" />
        Bloqueado
      </span>
    );
  }

  if (riesgoAceptado && mandatoActivo) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
        <ShieldCheck className="h-3.5 w-3.5" />
        Activo
      </span>
    );
  }

  if (mandatoActivo && !riesgoAceptado) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
        <FileSearch className="h-3.5 w-3.5" />
        Riesgo en Estudio
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
      <Clock className="h-3.5 w-3.5" />
      Pendiente
    </span>
  );
}
