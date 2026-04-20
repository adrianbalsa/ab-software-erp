export type PorteEstado = "pendiente" | "Entregado" | "facturado";

export type PorteListItem = {
  id: string;
  empresa_id: string;
  cliente_id?: string | null;
  fecha: string;
  origen: string;
  destino: string;
  km_estimados: number;
  estado: PorteEstado;
  precio_pactado?: number | null;
  descripcion?: string | null;
};

export type PorteDetail = PorteListItem & {
  bultos?: number;
  peso_ton?: number | null;
  vehiculo_id?: string | null;
  fecha_entrega_real?: string | null;
  nombre_consignatario_final?: string | null;
};

export type PodGeoStamp = {
  lat: number;
  lng: number;
  captured_at: string;
};

export type PodRegisterInput = {
  porteId: string;
  nombreConsignatario: string;
  dniConsignatario?: string;
  signatureDataUrl: string;
  photoUri: string;
  geostamp: PodGeoStamp;
};

export type PodRegisterResult = {
  estado: string;
  fecha_entrega_real?: string;
  mode: "patch" | "fallback_firmar_entrega" | "queued_offline";
};
