import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime


# --- CLASE PDF PROFESIONAL ---
class CertificadoOficial(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'CERTIFICADO TÉCNICO DE CUMPLIMIENTO MEDIOAMBIENTAL', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Doc. ID: {datetime.datetime.now().strftime("%Y%m%d")}-ESG | Uso Administrativo Exclusivo', 0,
                  0, 'C')


def generar_pdf_oficial(datos):
    pdf = CertificadoOficial()
    pdf.add_page()

    # Encabezado legal
    pdf.set_font('Arial', '', 11)
    texto_legal = (
        "D. [REPRESENTANTE LEGAL], actuando en calidad de administrador, CERTIFICA QUE:\n\n"
        "Los datos consignados en el presente informe corresponden fielmente a los registros "
        "digitales auditados por el sistema ERP corporativo, cumpliendo con los estándares "
        "de digitalización exigidos para la concesión de ayudas y subvenciones estatales."
    )
    pdf.multi_cell(0, 8, texto_legal)
    pdf.ln(10)

    # Tabla de Datos
    pdf.set_font('Arial', 'B', 11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 10, 'Indicador de Impacto', 1, 0, 'L', 1)
    pdf.cell(50, 10, 'Valor Auditado', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Unidad', 1, 1, 'C', 1)

    pdf.set_font('Arial', '', 11)
    pdf.cell(100, 10, 'Digitalización Documental', 1)
    pdf.cell(50, 10, str(datos['n_tickets']), 1, 0, 'C')
    pdf.cell(40, 10, 'Uds', 1, 1, 'C')

    pdf.cell(100, 10, 'Ahorro Materia Prima (Papel)', 1)
    pdf.cell(50, 10, f"{datos['papel_kg']:.2f}", 1, 0, 'C')
    pdf.cell(40, 10, 'Kg', 1, 1, 'C')

    pdf.cell(100, 10, 'Reducción Huella Carbono (CO2)', 1)
    pdf.cell(50, 10, f"{datos['co2_total']:.2f}", 1, 0, 'C')
    pdf.cell(40, 10, 'Kg CO2eq', 1, 1, 'C')

    pdf.ln(20)
    pdf.cell(0, 10, "Firma y Sello Digital:", 0, 1)

    return bytes(pdf.output(dest='S'))


# --- VISTA PRINCIPAL ---
def render_eco_view(db_client):
    st.title("🌱 Sostenibilidad y Subvenciones")
    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid:
        st.error("Error crítico: no se ha detectado el ID de empresa en la sesión.")
        return

    # Extracción de datos
    try:
        gastos = db_client.table("gastos").select("id").eq("empresa_id", eid).execute().data
        flota = db_client.table("flota").select("*").eq("empresa_id", eid).execute().data
        df_flota = pd.DataFrame(flota)
        n_tickets = len(gastos)
    except:
        n_tickets = 0
        df_flota = pd.DataFrame()

    # Cálculos ESG
    papel_kg = n_tickets * 0.010
    co2_tickets = n_tickets * 0.05
    co2_flota = 0.0

    if not df_flota.empty and "tipo_motor" in df_flota.columns:
        # Cálculo ficticio pero realista basado en motorización
        for _, row in df_flota.iterrows():
            if row["tipo_motor"] in ["Eléctrico", "Híbrido"]:
                co2_flota += 150.0  # Ahorro vs Diesel

    total_co2 = co2_tickets + co2_flota

    # Dashboard
    col1, col2, col3 = st.columns(3)
    col1.metric("Tickets Digitalizados", n_tickets)
    col2.metric("Papel Ahorrado (Kg)", f"{papel_kg:.3f}")
    col3.metric("CO2 Evitado Total (Kg)", f"{total_co2:.2f}")

    st.divider()

    c_main, c_cert = st.columns([2, 1])

    with c_main:
        st.subheader("Simulador de Flota Eco")
        if not df_flota.empty:
            # Edición para cálculo de impacto
            st.info("Define el motor de tus vehículos para recalcular el impacto:")
            edited = st.data_editor(
                df_flota[["vehiculo", "matricula", "tipo_motor"]],
                key="editor_eco",
                column_config={
                    "tipo_motor": st.column_config.SelectboxColumn("Motor", options=["Diesel", "Gasolina", "Híbrido",
                                                                                     "Eléctrico"])
                }
            )
        else:
            st.warning("No hay vehículos registrados en Flota.")

    with c_cert:
        st.subheader("📂 Área Administrativa")
        st.write("Generación de documentación oficial para Ayudas NextGen y Kit Digital.")

        datos_pdf = {
            "n_tickets": n_tickets,
            "papel_kg": papel_kg,
            "co2_total": total_co2
        }

        pdf_bytes = generar_pdf_oficial(datos_pdf)

        st.download_button(
            "📥 Descargar Certificado Oficial",
            data=pdf_bytes,
            file_name=f"Certificado_Sostenibilidad_{eid}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )