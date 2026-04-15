"use client";

import {
  Document,
  Image,
  Page,
  StyleSheet,
  Text,
  View,
} from "@react-pdf/renderer";

/** Payload alineado con ``GET /api/v1/facturas/{id}/pdf-data``. */
export type FacturaPdfPayload = {
  factura_id: number;
  numero_factura: string;
  num_factura_verifactu: string | null;
  tipo_factura: string | null;
  fecha_emision: string;
  emisor: { nombre: string; nif: string; direccion: string | null };
  receptor: { nombre: string; nif: string | null };
  lineas: Array<{
    concepto: string;
    cantidad: number;
    precio_unitario: number;
    importe: number;
  }>;
  base_imponible: number;
  tipo_iva_porcentaje: number;
  cuota_iva: number;
  total_factura: number;
  verifactu_qr_base64: string;
  verifactu_validation_url: string | null;
  verifactu_hash_audit: string;
  fingerprint_completo: string | null;
  fingerprint_hash?: string | null;
  hash_registro: string | null;
  aeat_csv_ultimo_envio: string | null;
};

const fmtEur = (n: number) =>
  new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
  }).format(n);

const fmtPct = (n: number) =>
  `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(n)} %`;

const styles = StyleSheet.create({
  page: {
    padding: 36,
    paddingBottom: 130,
    fontSize: 9,
    fontFamily: "Helvetica",
    color: "#27272a",
    backgroundColor: "#fafafa",
  },
  headerBand: {
    backgroundColor: "#18181b",
    padding: 14,
    marginBottom: 20,
    marginHorizontal: -36,
    marginTop: -36,
  },
  brand: {
    color: "#a1a1aa",
    fontSize: 8,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  titleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  facturaWord: {
    fontSize: 26,
    fontFamily: "Helvetica-Bold",
    color: "#fafafa",
    letterSpacing: -0.5,
  },
  metaRight: {
    alignItems: "flex-end",
  },
  metaLabel: { color: "#a1a1aa", fontSize: 8 },
  metaValue: { color: "#fafafa", fontSize: 11, fontFamily: "Helvetica-Bold" },
  columns: {
    flexDirection: "row",
    marginBottom: 20,
  },
  col: {
    flex: 1,
    backgroundColor: "#f4f4f5",
    borderRadius: 4,
    padding: 12,
    borderWidth: 1,
    borderColor: "#e4e4e7",
  },
  colTitle: {
    fontSize: 8,
    color: "#71717a",
    textTransform: "uppercase",
    marginBottom: 6,
    letterSpacing: 0.8,
  },
  colName: {
    fontSize: 11,
    fontFamily: "Helvetica-Bold",
    color: "#18181b",
    marginBottom: 4,
  },
  colLine: { fontSize: 9, color: "#3f3f46", marginBottom: 2 },
  tableHead: {
    flexDirection: "row",
    backgroundColor: "#e4e4e7",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
  },
  th: {
    fontSize: 8,
    fontFamily: "Helvetica-Bold",
    color: "#52525b",
    textTransform: "uppercase",
  },
  row: {
    flexDirection: "row",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#ffffff",
  },
  rowAlt: {
    flexDirection: "row",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#e4e4e7",
    backgroundColor: "#fafafa",
  },
  cConcept: { width: "46%" },
  cQty: { width: "12%", textAlign: "right" },
  cPrice: { width: "21%", textAlign: "right" },
  cAmt: { width: "21%", textAlign: "right", fontFamily: "Helvetica-Bold" },
  totalsWrap: {
    marginTop: 16,
    alignItems: "flex-end",
  },
  totalsBox: {
    width: 220,
    backgroundColor: "#f4f4f5",
    borderWidth: 1,
    borderColor: "#d4d4d8",
    borderRadius: 4,
    padding: 12,
  },
  totRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 4,
  },
  totLabel: { fontSize: 9, color: "#52525b" },
  totVal: { fontSize: 9, color: "#18181b" },
  totStrong: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#18181b",
  },
  totStrongLabel: { fontSize: 11, fontFamily: "Helvetica-Bold", color: "#18181b" },
  totStrongVal: { fontSize: 11, fontFamily: "Helvetica-Bold", color: "#18181b" },
  footer: {
    position: "absolute",
    bottom: 24,
    left: 36,
    right: 36,
    flexDirection: "row",
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#d4d4d8",
  },
  qrWrap: { marginRight: 14 },
  qr: { width: 72, height: 72 },
  qrPlaceholder: {
    width: 72,
    height: 72,
    backgroundColor: "#e4e4e7",
    justifyContent: "center",
    alignItems: "center",
  },
  legalBlock: { flex: 1, justifyContent: "center" },
  legalTitle: {
    fontSize: 8,
    fontFamily: "Helvetica-Bold",
    color: "#18181b",
    marginBottom: 4,
  },
  legalBody: { fontSize: 7, color: "#52525b", lineHeight: 1.35 },
  hashMono: { fontFamily: "Courier", fontSize: 7, color: "#3f3f46", marginTop: 4 },
  footNote: {
    marginTop: 10,
    fontSize: 6,
    color: "#a1a1aa",
    textAlign: "center",
  },
});

export function FacturaDocument({ data }: { data: FacturaPdfPayload }) {
  const fecha = String(data.fecha_emision).slice(0, 10);
  const numShow = data.num_factura_verifactu || data.numero_factura;

  return (
    <Document title={`Factura ${numShow}`} subject="Factura comercial VeriFactu">
      <Page size="A4" style={styles.page}>
        <View style={styles.headerBand}>
          <Text style={styles.brand}>AB Logistics OS</Text>
          <View style={styles.titleRow}>
            <Text style={styles.facturaWord}>FACTURA</Text>
            <View style={styles.metaRight}>
              <Text style={styles.metaLabel}>Número</Text>
              <Text style={styles.metaValue}>{numShow}</Text>
              <Text style={{ height: 6 }} />
              <Text style={styles.metaLabel}>Fecha emisión</Text>
              <Text style={styles.metaValue}>{fecha}</Text>
              {data.tipo_factura ? (
                <>
                  <Text style={{ height: 4 }} />
                  <Text style={styles.metaLabel}>Tipo</Text>
                  <Text style={styles.metaValue}>{data.tipo_factura}</Text>
                </>
              ) : null}
            </View>
          </View>
        </View>

        <View style={styles.columns}>
          <View style={[styles.col, { marginRight: 12 }]}>
            <Text style={styles.colTitle}>Emisor</Text>
            <Text style={styles.colName}>{data.emisor.nombre}</Text>
            <Text style={styles.colLine}>NIF: {data.emisor.nif || "—"}</Text>
            {data.emisor.direccion ? (
              <Text style={styles.colLine}>{data.emisor.direccion}</Text>
            ) : null}
          </View>
          <View style={[styles.col, { marginRight: 0 }]}>
            <Text style={styles.colTitle}>Cliente</Text>
            <Text style={styles.colName}>{data.receptor.nombre}</Text>
            <Text style={styles.colLine}>NIF: {data.receptor.nif || "—"}</Text>
          </View>
        </View>

        <View style={{ borderRadius: 4, overflow: "hidden", borderWidth: 1, borderColor: "#e4e4e7" }}>
          <View style={styles.tableHead}>
            <Text style={[styles.th, styles.cConcept]}>Concepto</Text>
            <Text style={[styles.th, styles.cQty]}>Cant.</Text>
            <Text style={[styles.th, styles.cPrice]}>Precio</Text>
            <Text style={[styles.th, styles.cAmt]}>Importe</Text>
          </View>
          {(data.lineas.length ? data.lineas : [{ concepto: "—", cantidad: 0, precio_unitario: 0, importe: 0 }]).map(
            (ln, i) => (
              <View key={i} style={i % 2 === 0 ? styles.row : styles.rowAlt}>
                <Text style={[styles.cConcept, { fontSize: 8 }]}>{ln.concepto}</Text>
                <Text style={[styles.cQty, { fontSize: 8 }]}>{ln.cantidad}</Text>
                <Text style={[styles.cPrice, { fontSize: 8 }]}>{fmtEur(ln.precio_unitario)}</Text>
                <Text style={[styles.cAmt, { fontSize: 8 }]}>{fmtEur(ln.importe)}</Text>
              </View>
            ),
          )}
        </View>

        <View style={styles.totalsWrap}>
          <View style={styles.totalsBox}>
            <View style={styles.totRow}>
              <Text style={styles.totLabel}>Base imponible</Text>
              <Text style={styles.totVal}>{fmtEur(data.base_imponible)}</Text>
            </View>
            <View style={styles.totRow}>
              <Text style={styles.totLabel}>IVA ({fmtPct(data.tipo_iva_porcentaje)})</Text>
              <Text style={styles.totVal}>{fmtEur(data.cuota_iva)}</Text>
            </View>
            <View style={styles.totStrong}>
              <Text style={styles.totStrongLabel}>Total a pagar</Text>
              <Text style={styles.totStrongVal}>{fmtEur(data.total_factura)}</Text>
            </View>
          </View>
        </View>

        <View style={styles.footer} wrap={false}>
          <View style={styles.qrWrap}>
            {data.verifactu_qr_base64 ? (
              <Image
                src={`data:image/png;base64,${data.verifactu_qr_base64}`}
                style={styles.qr}
              />
            ) : (
              <View style={styles.qrPlaceholder}>
                <Text style={{ fontSize: 8, color: "#71717a" }}>QR</Text>
              </View>
            )}
          </View>
          <View style={styles.legalBlock}>
            <Text style={styles.legalTitle}>VeriFactu · AEAT</Text>
            <Text style={styles.legalBody}>
              Factura verificable en la sede electrónica de la AEAT. Escanee el código para
              comprobar la autenticidad del registro.
            </Text>
            {data.verifactu_hash_audit ? (
              <Text style={styles.hashMono}>Huella (auditoría): {data.verifactu_hash_audit}</Text>
            ) : null}
            {data.verifactu_validation_url ? (
              <Text style={[styles.legalBody, { marginTop: 4 }]}>
                {data.verifactu_validation_url.length > 120
                  ? `${data.verifactu_validation_url.slice(0, 120)}…`
                  : data.verifactu_validation_url}
              </Text>
            ) : null}
          </View>
        </View>

        <Text style={styles.footNote} fixed>
          Documento generado electrónicamente · AB Logistics OS · Importes con redondeo bancario (HALF_EVEN)
        </Text>
      </Page>
    </Document>
  );
}
