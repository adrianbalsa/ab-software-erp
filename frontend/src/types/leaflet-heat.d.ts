/**
 * Tipos para el plugin `leaflet.heat` (side-effect: muta el namespace Leaflet en runtime).
 * @see https://github.com/Leaflet/Leaflet.heat
 */
import type { Layer } from "leaflet";

declare module "leaflet" {
  export interface HeatLayerPluginOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }

  /**
   * Creador de capa de mapa de calor (registrado por `leaflet.heat` sobre el objeto `L` del bundle).
   * Se fusiona con las exportaciones nombradas de `@types/leaflet` para que `import L from "leaflet"`
   * reconozca `L.heatLayer` bajo `esModuleInterop`.
   */
  export function heatLayer(
    latlngs: Array<[number, number] | [number, number, number]>,
    options?: HeatLayerPluginOptions,
  ): Layer;
}

/** Módulo sin tipos propios: solo ejecuta el patch en `L`. */
declare module "leaflet.heat";
