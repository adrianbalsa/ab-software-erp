export type GastoCategoria = "combustible" | "materiales" | "servicios" | "otros";

export type GastoRecent = {
  id: string;
  proveedor: string;
  fecha: string;
  total_chf: number;
  categoria: GastoCategoria | string;
  concepto?: string | null;
  moneda: string;
  evidencia_url?: string | null;
  porte_id?: string | null;
};

export type GastoOcrExtract = {
  proveedor?: string | null;
  cif?: string | null;
  base_imponible?: number | null;
  iva?: number | null;
  total?: number | null;
  fecha?: string | null;
};

export type GastoCreateInput = {
  proveedor: string;
  fecha: string;
  total_chf: number;
  categoria: GastoCategoria;
  moneda: string;
  concepto?: string;
  nif_proveedor?: string;
  iva?: number;
  total_eur?: number;
  porte_id?: string;
  ticketUri: string;
};
