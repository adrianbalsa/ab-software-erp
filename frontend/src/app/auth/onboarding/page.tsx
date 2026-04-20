"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import RiskAssessmentCard from "@/components/auth/RiskAssessmentCard";
import { Loader2 } from "lucide-react";
import { fetchPortalMyRisk, postPortalAcceptRisk, type PortalOnboardingMyRisk } from "@/lib/api";

function OnboardingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token"); // Token de la invitación de Supabase
  
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [riskData, setRiskData] = useState<PortalOnboardingMyRisk | null>(null);

  useEffect(() => {
    async function fetchOnboardingData() {
      try {
        const data = await fetchPortalMyRisk();
        setRiskData(data);
      } catch (error) {
        setFeedback({
          tone: "error",
          message: "Error al cargar la invitación. Contacte con soporte.",
        });
      } finally {
        setLoading(false);
      }
    }

    if (token) {
      void fetchOnboardingData();
      return;
    }
    setLoading(false);
  }, [token]);

  const handleAcceptRisk = async () => {
    setAccepting(true);
    setFeedback(null);
    try {
      await postPortalAcceptRisk();
      setFeedback({ tone: "success", message: "Condiciones aceptadas correctamente." });
      router.push(`/auth/set-password?token=${token}`);
    } catch (error) {
      setFeedback({ tone: "error", message: "No se pudo procesar la aceptación." });
    } finally {
      setAccepting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Bienvenido al Portal</h1>
          <p className="text-slate-600">Complete su proceso de admisión para empezar a operar.</p>
        </div>
        {feedback ? (
          <p
            className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
              feedback.tone === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {feedback.message}
          </p>
        ) : null}

        {riskData && (
          <RiskAssessmentCard
            score={riskData.score}
            creditLimitEur={riskData.creditLimitEur}
            collectionTerms={riskData.collectionTerms}
            reasons={riskData.reasons}
            onConfirm={handleAcceptRisk}
            ctaLabel={accepting ? "Guardando..." : "Guardar y continuar"}
            isLoading={accepting}
          />
        )}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      }
    >
      <OnboardingContent />
    </Suspense>
  );
}