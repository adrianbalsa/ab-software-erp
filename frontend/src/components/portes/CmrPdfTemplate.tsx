"use client";

import type { ReactNode } from "react";
import {
  Document,
  Page,
  StyleSheet,
  Text,
  View,
  pdf,
} from "@react-pdf/renderer";
import type { CmrDataOut } from "@/lib/api";

const styles = StyleSheet.create({
  page: {
    padding: 10,
    fontSize: 7,
    fontFamily: "Helvetica",
    color: "#111",
  },
  title: {
    fontSize: 11,
    textAlign: "center",
    marginBottom: 6,
    fontFamily: "Helvetica-Bold",
  },
  subtitle: {
    fontSize: 7,
    textAlign: "center",
    marginBottom: 8,
    color: "#333",
  },
  row: {
    flexDirection: "row",
    alignItems: "stretch",
  },
  cell: {
    borderWidth: 1,
    borderColor: "#000",
    padding: 4,
    flexGrow: 1,
    flexBasis: 0,
    minHeight: 52,
    borderStyle: "solid",
  },
  cellSmall: {
    minHeight: 36,
  },
  cellSig: {
    minHeight: 64,
  },
  num: {
    fontSize: 6,
    fontFamily: "Helvetica-Bold",
    marginBottom: 2,
  },
  body: {
    fontSize: 7,
    fontFamily: "Helvetica",
    lineHeight: 1.25,
  },
});

function fmtParty(
  p: CmrDataOut["casilla_1_remitente"],
  empty: string,
): string {
  const lines = [
    p.nombre ?? "",
    p.nif ? `NIF/CIF: ${p.nif}` : "",
    p.direccion ?? "",
    p.pais ? `País: ${p.pais}` : "",
  ].filter((x) => x.length > 0);
  return lines.length ? lines.join("\n") : empty;
}

function fmtLugarFecha(lf: CmrDataOut["casilla_4_lugar_fecha_toma_carga"]): string {
  const d = lf.fecha ?? "";
  const parts = [lf.lugar ? `Lugar: ${lf.lugar}` : "", d ? `Fecha: ${d}` : ""].filter(
    Boolean,
  );
  return parts.join("\n");
}

function fmtMerc(m: CmrDataOut["casilla_6_12_mercancia"], km: number | null): string {
  const lines: string[] = [];
  if (m.descripcion) lines.push(`Mercancía: ${m.descripcion}`);
  if (m.bultos != null) lines.push(`Bultos: ${m.bultos}`);
  if (m.peso_kg != null) lines.push(`Peso (kg): ${m.peso_kg.toLocaleString("es-ES")}`);
  else if (m.peso_ton != null) lines.push(`Peso (t): ${m.peso_ton}`);
  if (m.matricula_vehiculo) lines.push(`Matrícula: ${m.matricula_vehiculo}`);
  if (m.nombre_vehiculo) lines.push(`Vehículo: ${m.nombre_vehiculo}`);
  if (m.nombre_conductor) lines.push(`Conductor: ${m.nombre_conductor}`);
  if (km != null) lines.push(`Km ruta (est.): ${km}`);
  return lines.length ? lines.join("\n") : "—";
}

function Cell({
  n,
  children,
  small,
  sig,
}: {
  n: number;
  children: ReactNode;
  small?: boolean;
  sig?: boolean;
}) {
  return (
    <View
      style={[
        styles.cell,
        small ? styles.cellSmall : {},
        sig ? styles.cellSig : {},
      ]}
    >
      <Text style={styles.num}>{n}</Text>
      {children}
    </View>
  );
}

/** Documento CMR (estructura tipo cajas 1–24; 22–24 reservadas para firmas). */
export function CmrDocument({ data }: { data: CmrDataOut }) {
  const m = data.casilla_6_12_mercancia;
  const km = data.km_estimados;

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <Text style={styles.title}>Carta de porte (CMR) — Convenio Ginebra 1956</Text>
        <Text style={styles.subtitle}>
          Porte {data.porte_id} · Documento informativo; revisar datos antes de firmar.
        </Text>

        <View style={styles.row}>
          <Cell n={1}>
            <Text style={styles.body}>{fmtParty(data.casilla_1_remitente, "Remitente: —")}</Text>
          </Cell>
          <Cell n={2}>
            <Text style={styles.body}>
              {fmtParty(data.casilla_2_consignatario, "Consignatario: —")}
            </Text>
          </Cell>
          <Cell n={3}>
            <Text style={styles.body}>
              {data.casilla_3_lugar_entrega_mercancia ?? "—"}
            </Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={4}>
            <Text style={styles.body}>{fmtLugarFecha(data.casilla_4_lugar_fecha_toma_carga)}</Text>
          </Cell>
          <Cell n={5} small>
            <Text style={styles.body}>Documentos adjuntos: —</Text>
          </Cell>
          <Cell n={6} small>
            <Text style={styles.body}>Marcas y núm.: —</Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={7} small>
            <Text style={styles.body}>
              {m.bultos != null ? `Bultos: ${m.bultos}` : "Bultos: —"}
            </Text>
          </Cell>
          <Cell n={8} small>
            <Text style={styles.body}>Embalaje: —</Text>
          </Cell>
          <Cell n={9}>
            <Text style={styles.body}>
              {m.descripcion ?? "Naturaleza de la mercancía: —"}
            </Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={10} small>
            <Text style={styles.body}>N.º estadístico: —</Text>
          </Cell>
          <Cell n={11}>
            <Text style={styles.body}>
              {m.peso_kg != null
                ? `Peso bruto (kg): ${m.peso_kg.toLocaleString("es-ES")}`
                : m.peso_ton != null
                  ? `Peso (t): ${m.peso_ton}`
                  : "Peso: —"}
            </Text>
          </Cell>
          <Cell n={12} small>
            <Text style={styles.body}>
              {m.volumen_m3 != null ? `Volumen (m³): ${m.volumen_m3}` : "Volumen: —"}
            </Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={13}>
            <Text style={styles.body}>Instrucciones del expedidor: —</Text>
          </Cell>
          <Cell n={14} small>
            <Text style={styles.body}>Reservas: —</Text>
          </Cell>
          <Cell n={15} small>
            <Text style={styles.body}>Estipulaciones: —</Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={16}>
            <Text style={styles.body}>
              {fmtParty(data.casilla_16_transportista, "Transportista: —")}
            </Text>
          </Cell>
          <Cell n={17} small>
            <Text style={styles.body}>Transportistas sucesivos: —</Text>
          </Cell>
          <Cell n={18} small>
            <Text style={styles.body}>Reservas sucesivas: —</Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={19}>
            <Text style={styles.body}>Acuerdos especiales: —</Text>
          </Cell>
          <Cell n={20} small>
            <Text style={styles.body}>A pagar por: —</Text>
          </Cell>
          <Cell n={21} small>
            <Text style={styles.body}>
              {km != null ? `Km estimados: ${km}` : "Establecido en: —"}
            </Text>
          </Cell>
        </View>

        <View style={styles.row}>
          <Cell n={22} sig>
            <View />
          </Cell>
          <Cell n={23} sig>
            <View />
          </Cell>
          <Cell n={24} sig>
            <View />
          </Cell>
        </View>

        <View style={{ marginTop: 6 }}>
          <Text style={{ fontSize: 6, color: "#555" }}>
            Resumen mercancía / vehículo: {fmtMerc(m, km)}
          </Text>
        </View>
      </Page>
    </Document>
  );
}

export async function generateCmrPdfBlob(data: CmrDataOut): Promise<Blob> {
  return pdf(<CmrDocument data={data} />).toBlob();
}
