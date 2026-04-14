"use client";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Wrench } from "lucide-react";

export interface TruckEfficiency {
  matricula: string;
  marca_modelo: string;
  km_totales: number;
  litros_totales: number;
  consumo_medio: number;
  coste_por_km: number;
  alerta_mantenimiento: boolean;
  margen_generado: number;
}

interface FleetEfficiencyTableProps {
  data: TruckEfficiency[];
}

export function FleetEfficiencyTable({ data }: FleetEfficiencyTableProps) {
  // Configuración de colores para el consumo
  const getConsumptionColor = (consumo: number) => {
    if (consumo < 28) return "bg-emerald-500";
    if (consumo > 35) return "bg-red-500";
    return "bg-yellow-500";
  };

  const getConsumptionProgress = (consumo: number) => {
    // Escala del 0 al 50L/100km para la barra
    const value = (consumo / 50) * 100;
    return Math.min(Math.max(value, 0), 100);
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Vehículo</TableHead>
            <TableHead className="text-right">Km Totales</TableHead>
            <TableHead className="w-[200px]">Consumo (L/100km)</TableHead>
            <TableHead className="text-right">Coste/Km</TableHead>
            <TableHead className="text-right">Margen</TableHead>
            <TableHead className="text-center">Estado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-6 text-muted-foreground">
                No hay datos de eficiencia de flota disponibles.
              </TableCell>
            </TableRow>
          ) : (
            data.map((truck) => (
              <TableRow key={truck.matricula}>
                <TableCell>
                  <div className="font-medium">{truck.matricula}</div>
                  <div className="text-xs text-muted-foreground">{truck.marca_modelo}</div>
                </TableCell>
                <TableCell className="text-right">
                  {new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(truck.km_totales)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="w-12 text-right font-medium">{truck.consumo_medio.toFixed(1)}</span>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="w-full">
                            <Progress 
                              value={getConsumptionProgress(truck.consumo_medio)} 
                              indicatorClassName={getConsumptionColor(truck.consumo_medio)}
                              className="h-2"
                            />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{truck.consumo_medio.toFixed(1)} L / 100km</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  {new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(truck.coste_por_km)}
                </TableCell>
                <TableCell className="text-right font-medium">
                  {new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(truck.margen_generado)}
                </TableCell>
                <TableCell className="text-center">
                  {truck.alerta_mantenimiento ? (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex cursor-help items-center gap-1 rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-semibold text-red-600 transition-colors hover:bg-red-500/20 border border-red-200">
                            <Wrench className="h-3 w-3" />
                            <span>Revisión</span>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Ha superado los 30.000 km desde la última revisión</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-green-500/10 px-2.5 py-0.5 text-xs font-semibold text-green-700 transition-colors hover:bg-green-500/20 border border-green-200">
                      Ok
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
