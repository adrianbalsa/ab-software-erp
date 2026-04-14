"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { API_BASE, apiFetch, parseApiError, postAuthOnboardingSetup } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type OnboardingFormValues = {
  company_name: string;
  cif: string;
  address: string;
  initial_fleet_type: string[];
  target_margin_pct: number;
};

const FLEET_OPTIONS = [
  "Articulado > 40t",
  "Rígido 12-24t",
  "Furgoneta LCV",
  "Frigorífico",
  "Lona / tautliner",
] as const;

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);
  const {
    register,
    trigger,
    getValues,
    handleSubmit,
    formState: { errors },
  } = useForm<OnboardingFormValues>({
    defaultValues: {
      company_name: "",
      cif: "",
      address: "",
      initial_fleet_type: [],
      target_margin_pct: 18,
    },
    mode: "onChange",
  });

  useEffect(() => {
    if (step < 1 || step > 3) setStep(1);
  }, [step]);

  useEffect(() => {
    let isMounted = true;
    const verifyOnboardingState = async () => {
      try {
        const res = await apiFetch(`${API_BASE}/empresa/quota`, { credentials: "include" });
        if (!isMounted) return;
        if (res.ok) {
          router.replace("/dashboard");
          return;
        }
        if (res.status !== 401 && res.status !== 403) {
          setError(await parseApiError(res));
        }
      } catch {
        // ignore and let user continue with onboarding.
      } finally {
        if (isMounted) setCheckingStatus(false);
      }
    };
    void verifyOnboardingState();
    return () => {
      isMounted = false;
    };
  }, [router]);

  const progressLabel = useMemo(() => `Paso ${step} de 3`, [step]);

  const nextStep = async () => {
    setError(null);
    if (step === 1) {
      const ok = await trigger(["company_name", "cif", "address"]);
      if (!ok) return;
    }
    if (step === 2) {
      const fleet = getValues("initial_fleet_type");
      if (!fleet || fleet.length === 0) {
        setError("Selecciona al menos un tipo de vehículo habitual.");
        return;
      }
    }
    setStep((s) => Math.min(3, s + 1));
  };

  const prevStep = () => {
    setError(null);
    setStep((s) => Math.max(1, s - 1));
  };

  const onSubmit = async (values: OnboardingFormValues) => {
    setError(null);
    setSubmitting(true);
    try {
      await postAuthOnboardingSetup({
        company_name: values.company_name.trim(),
        cif: values.cif.trim().toUpperCase(),
        address: values.address.trim(),
        initial_fleet_type: values.initial_fleet_type.join(", "),
        target_margin_pct: Number(values.target_margin_pct),
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo completar el onboarding.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 px-4 py-8">
      <Card className="w-full max-w-2xl border border-zinc-800 bg-zinc-900 text-zinc-100">
        <CardHeader>
          <CardTitle>Configuración inicial de AB Logistics OS</CardTitle>
          <CardDescription className="text-zinc-400">{progressLabel}</CardDescription>
        </CardHeader>
        <CardContent>
          {checkingStatus ? (
            <p className="text-sm text-zinc-400">Validando estado de onboarding...</p>
          ) : (
          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            {step === 1 && (
              <section className="space-y-4">
                <h2 className="text-sm font-semibold text-zinc-300">Datos de la Empresa</h2>
                <div className="space-y-2">
                  <label className="text-sm text-zinc-300" htmlFor="company_name">
                    Razón social
                  </label>
                  <Input
                    id="company_name"
                    {...register("company_name", { required: "La razón social es obligatoria." })}
                  />
                  {errors.company_name && <p className="text-xs text-red-400">{errors.company_name.message}</p>}
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-zinc-300" htmlFor="cif">
                    CIF
                  </label>
                  <Input id="cif" {...register("cif", { required: "El CIF es obligatorio." })} />
                  {errors.cif && <p className="text-xs text-red-400">{errors.cif.message}</p>}
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-zinc-300" htmlFor="address">
                    Dirección
                  </label>
                  <Input id="address" {...register("address", { required: "La dirección es obligatoria." })} />
                  {errors.address && <p className="text-xs text-red-400">{errors.address.message}</p>}
                </div>
              </section>
            )}

            {step === 2 && (
              <section className="space-y-4">
                <h2 className="text-sm font-semibold text-zinc-300">Configuración Logística</h2>
                <p className="text-sm text-zinc-400">Selecciona los tipos de vehículos habituales.</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {FLEET_OPTIONS.map((item) => (
                    <label key={item} className="flex items-center gap-2 rounded-md border border-zinc-700 p-3 text-sm">
                      <input type="checkbox" value={item} {...register("initial_fleet_type")} />
                      <span>{item}</span>
                    </label>
                  ))}
                </div>
              </section>
            )}

            {step === 3 && (
              <section className="space-y-4">
                <h2 className="text-sm font-semibold text-zinc-300">Preferencias del Radar</h2>
                <div className="space-y-2">
                  <label className="text-sm text-zinc-300" htmlFor="target_margin_pct">
                    Margen objetivo (%)
                  </label>
                  <Input
                    id="target_margin_pct"
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    {...register("target_margin_pct", { valueAsNumber: true, min: 0, max: 100 })}
                  />
                </div>
              </section>
            )}

            {error && <p className="text-sm text-red-400">{error}</p>}
          </form>
          )}
        </CardContent>
        <CardFooter className="justify-between border-zinc-800 bg-zinc-900">
          <Button variant="outline" onClick={prevStep} disabled={checkingStatus || step === 1 || submitting}>
            Atrás
          </Button>
          {step < 3 ? (
            <Button onClick={nextStep} disabled={checkingStatus || submitting}>
              Continuar
            </Button>
          ) : (
            <Button onClick={handleSubmit(onSubmit)} disabled={checkingStatus || submitting}>
              {submitting ? "Configurando..." : "Finalizar onboarding"}
            </Button>
          )}
        </CardFooter>
      </Card>
    </main>
  );
}
