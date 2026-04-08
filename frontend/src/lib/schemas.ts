import { z } from "zod";

const IsoDateSchema = z.string().min(8);

export const PorteSchema = z.object({
  id: z.string().min(1),
  cliente_id: z.string().min(1).nullable().optional(),
  cliente_nombre: z.string().min(1).nullable().optional(),
  fecha: IsoDateSchema,
  origen: z.string().min(1),
  destino: z.string().min(1),
  km_estimados: z.number().nullable().optional(),
  precio_pactado: z.number().nullable().optional(),
  estado: z.enum(["pendiente", "en_curso", "entregado", "facturado", "cancelado"]).or(z.string().min(1)),
  factura_id: z.string().min(1).nullable().optional(),
  created_at: z.string().datetime().nullable().optional(),
});

export const ClienteSchema = z.object({
  id: z.string().min(1),
  nombre: z.string().min(1),
  nif: z.string().min(1).nullable().optional(),
  razon_social: z.string().min(1).nullable().optional(),
  email: z.string().email().nullable().optional(),
  telefono: z.string().min(1).nullable().optional(),
  direccion: z.string().min(1).nullable().optional(),
  created_at: z.string().datetime().nullable().optional(),
});

export const DashboardStatsSchema = z.object({
  km_estimados: z.number().default(0),
  portes_count: z.number().default(0),
  clientes_activos: z.number().default(0),
  facturacion_estimada: z.number().default(0),
  ebitda: z.number().default(0),
  ingresos: z.number().default(0),
  gastos: z.number().default(0),
  bultos: z.number().default(0),
});

export const EfficiencyRankingItemSchema = z.object({
  matricula: z.string().min(1),
  marca_modelo: z.string().min(1),
  km_totales: z.number(),
  litros_totales: z.number(),
  consumo_medio: z.number(),
  coste_por_km: z.number(),
  alerta_mantenimiento: z.boolean(),
  margen_generado: z.number(),
});

export const EfficiencyRankingSchema = z.array(EfficiencyRankingItemSchema);

export type Porte = z.infer<typeof PorteSchema>;
export type Cliente = z.infer<typeof ClienteSchema>;
export type DashboardStats = z.infer<typeof DashboardStatsSchema>;
export type EfficiencyRankingItem = z.infer<typeof EfficiencyRankingItemSchema>;
