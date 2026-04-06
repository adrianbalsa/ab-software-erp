"use client";

import Joyride, { type CallBackProps, STATUS, type Step } from "react-joyride";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useOnboarding } from "@/hooks/useOnboarding";
import { useRole } from "@/hooks/useRole";
import { isOwnerLike } from "@/lib/api";

const STEPS: Step[] = [
  {
    target: "#tour-nav-dashboard",
    placement: "right",
    disableBeacon: true,
    content:
      "Bienvenido a AB Logistics OS. Tu centro de mando financiero y operativo. Empecemos a rodar.",
  },
  {
    target: "#tour-nav-flota",
    placement: "right",
    content:
      "Tu mayor activo. Añade aquí tu primer camión para empezar a asignarle rutas y controlar su rentabilidad.",
  },
  {
    target: "#tour-nav-clientes",
    placement: "right",
    content:
      "Sin clientes no hay facturas. Registra tu primer cliente para poder cotizarle un transporte.",
  },
  {
    target: "#tour-nav-portes",
    placement: "right",
    content:
      "El corazón del negocio. Crea un porte, asígnale el camión y deja que nuestro Math Engine calcule el margen exacto.",
  },
  {
    target: "#tour-nav-finanzas",
    placement: "right",
    content:
      "Cuando la mercancía se entregue, aquí generarás facturas inalterables con VeriFactu en un solo clic. ¡A facturar!",
  },
];

export function TourGuide() {
  const pathname = usePathname();
  const { role } = useRole();
  const { completed, hydrated, markComplete } = useOnboarding();
  const [run, setRun] = useState(false);

  const shouldOfferTour = isOwnerLike(role) && hydrated && !completed;

  useEffect(() => {
    if (!shouldOfferTour || pathname !== "/dashboard") {
      return;
    }
    const id = window.setTimeout(() => setRun(true), 600);
    return () => window.clearTimeout(id);
  }, [shouldOfferTour, pathname]);

  const handleCallback = useCallback(
    (data: CallBackProps) => {
      const { status } = data;
      if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
        setRun(false);
        markComplete();
      }
    },
    [markComplete],
  );

  const styles = useMemo(
    () => ({
      options: {
        primaryColor: "#10b981",
        textColor: "#e4e4e7",
        backgroundColor: "#18181b",
        overlayColor: "rgba(0,0,0,0.75)",
        arrowColor: "#18181b",
        zIndex: 10050,
      } as const,
      tooltip: {
        borderRadius: 12,
        padding: 16,
      },
      tooltipContainer: {
        textAlign: "left" as const,
      },
      buttonNext: {
        backgroundColor: "#10b981",
        color: "#022c22",
        fontWeight: 600,
        borderRadius: 8,
        padding: "8px 14px",
        fontSize: 13,
      },
      buttonBack: {
        color: "#a1a1aa",
        marginRight: 8,
        fontSize: 13,
      },
      buttonSkip: {
        color: "#71717a",
        fontSize: 12,
      },
      buttonClose: {
        color: "#a1a1aa",
      },
    }),
    [],
  );

  if (!shouldOfferTour && !run) {
    return null;
  }

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      showProgress
      showSkipButton
      scrollToFirstStep
      disableScrollParentFix={false}
      callback={handleCallback}
      styles={styles}
      locale={{
        back: "Atrás",
        close: "Cerrar",
        last: "Finalizar",
        next: "Siguiente",
        skip: "Saltar tour",
      }}
    />
  );
}
