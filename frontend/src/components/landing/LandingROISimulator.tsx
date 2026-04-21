"use client";

import { useMemo, useState } from "react";
import { Calculator, Clock, Euro, Leaf } from "lucide-react";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { FadeInSection } from "./FadeInSection";

export function LandingROISimulator() {
  const [trucks, setTrucks] = useState(8);
  const [kmPerTruck, setKmPerTruck] = useState(3200);
  const { catalog, locale } = useOptionalLocaleCatalog();
  const l = catalog.landing.roi;
  const localeTag = locale === "en" ? "en-US" : "es-ES";

  const { hoursSaved, moneySaved, esgKg } = useMemo(() => {
    const hours = trucks * 4;
    const money = hours * 25;
    const totalKmMonth = trucks * kmPerTruck;
    const esg = totalKmMonth * 0.085;
    return {
      hoursSaved: hours,
      moneySaved: money,
      esgKg: esg,
    };
  }, [trucks, kmPerTruck]);

  return (
    <FadeInSection id="roi-simulator" className="scroll-mt-24 px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-400 max-w-xl mx-auto text-sm sm:text-base">{l.subtitle}</p>
        </div>

        <div className="rounded-3xl border border-zinc-800 bg-gradient-to-b from-zinc-900/90 to-zinc-950 p-6 sm:p-10 shadow-2xl shadow-black/40">
          <div className="grid gap-10 lg:grid-cols-2 lg:gap-12">
            <div className="space-y-8">
              <div>
                <label className="flex justify-between text-sm font-medium text-zinc-300 mb-2">
                  <span>{l.fleetSize}</span>
                  <span className="text-emerald-400 font-mono tabular-nums">
                    {trucks} {l.trucksSuffix}
                  </span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={trucks}
                  onChange={(e) => setTrucks(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer accent-emerald-500 bg-zinc-700"
                />
                <p className="mt-1 text-xs text-zinc-500">{l.fleetRangeHint}</p>
              </div>
              <div>
                <label className="flex justify-between text-sm font-medium text-zinc-300 mb-2">
                  <span>{l.kmPerTruck}</span>
                  <span className="text-blue-400 font-mono tabular-nums">{kmPerTruck.toLocaleString(localeTag)} km</span>
                </label>
                <input
                  type="range"
                  min={500}
                  max={12000}
                  step={100}
                  value={kmPerTruck}
                  onChange={(e) => setKmPerTruck(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer accent-blue-500 bg-zinc-700"
                />
                <p className="mt-1 text-xs text-zinc-500">{l.kmRangeHint}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-start gap-4 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-500/15 text-blue-400">
                  <Clock className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{l.adminSaved}</p>
                  <p className="text-2xl font-bold text-white tabular-nums">
                    {hoursSaved} <span className="text-sm font-normal text-zinc-400">{l.hoursPerMonth}</span>
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">{l.adminSavedHint}</p>
                </div>
              </div>
              <div className="flex items-start gap-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
                  <Euro className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{l.economicSaving}</p>
                  <p className="text-2xl font-bold text-emerald-400 tabular-nums">
                    {moneySaved.toLocaleString(localeTag, {
                      style: "currency",
                      currency: "EUR",
                      maximumFractionDigits: 0,
                    })}
                    <span className="text-sm font-normal text-zinc-400"> {l.monthSuffix}</span>
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">{l.economicSavingHint}</p>
                </div>
              </div>
              <div className="flex items-start gap-4 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-600/15 text-emerald-400">
                  <Leaf className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">{l.trackedEsg}</p>
                  <p className="text-2xl font-bold text-white tabular-nums">
                    {esgKg.toLocaleString(localeTag, { maximumFractionDigits: 0 })}{" "}
                    <span className="text-sm font-normal text-zinc-400">{l.kgPerMonth}</span>
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">{l.trackedEsgHint}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/50 px-4 py-4 sm:px-6">
            <Calculator className="h-5 w-5 text-blue-400 shrink-0" />
            <p className="text-center text-sm sm:text-base text-zinc-200">
              {l.summaryPrefix}{" "}
              <strong className="text-emerald-400 tabular-nums">
                {moneySaved.toLocaleString(localeTag, {
                  style: "currency",
                  currency: "EUR",
                  maximumFractionDigits: 0,
                })}
              </strong>{" "}
              {l.summarySuffix}
            </p>
          </div>
        </div>
      </div>
    </FadeInSection>
  );
}
