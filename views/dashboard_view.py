import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime


# Función auxiliar para generar enlaces firmados (Time-bound)
def generar_enlace_temporal(ruta_archivo, db_client):
    if not ruta_archivo or pd.isna(ruta_archivo):
        return "Sin evidencia"
    try:
        res = db_client.storage.from_("tickets").create_signed_url(ruta_archivo, 3600)
        return res['signedURL']
    except Exception:
        return "Error enlace"


def render_dashboard(db):
    st.title("📊 Cuadro de Mando Integral (Business Intelligence)")

    if 'empresaid' not in st.session_state:
        st.error("⚠️ Sesión inválida. Por favor, reinicia el sistema.")
        return

    eid = st.session_state.empresaid
    usuario = st.session_state.username

    # 1. CARGA DE DATOS SINCRONIZADA
    with st.spinner("🔄 Procesando analítica en tiempo real..."):
        try:
            t_gastos = db.table("gastos").select("*").eq("empresa_id", eid).execute()
            t_ingresos = db.table("presupuestos").select("*").eq("empresa_id", eid).eq("estado", "Facturado").execute()
            t_flota = db.table("flota").select("*").eq("empresa_id", eid).execute()
            t_stock = db.table("inventario").select("*").eq("empresa_id", eid).execute()

            df_gastos = pd.DataFrame(t_gastos.data)
            df_ingresos = pd.DataFrame(t_ingresos.data)
            df_flota = pd.DataFrame(t_flota.data)
            df_stock = pd.DataFrame(t_stock.data)

        except Exception as e:
            st.error(f"Error de conexión DB: {e}")
            return

    # 2. KPIs FINANCIEROS
    st.markdown(f"### 💰 Situación Financiera: {usuario}")

    total_gastos = df_gastos["total_chf"].sum() if not df_gastos.empty else 0.0
    total_ventas = df_ingresos["total_final"].sum() if not df_ingresos.empty else 0.0
    resultado_neto = total_ventas - total_gastos
    margen_beneficio = (resultado_neto / total_ventas * 100) if total_ventas > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Volumen de Ventas", f"{total_ventas:,.2f} €", delta="Facturado")
    kpi2.metric("Gastos Operativos", f"{total_gastos:,.2f} €", delta="-Salidas", delta_color="inverse")
    kpi3.metric("Resultado Neto (EBIT)", f"{resultado_neto:,.2f} €", delta=f"{margen_beneficio:.1f}% Margen")
    activos_flota = len(df_flota) if not df_flota.empty else 0
    kpi4.metric("Activos en Flota", f"{activos_flota} uds")

    st.divider()

    # 3. ANÁLISIS VISUAL
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        st.subheader("📉 Desglose de Gastos")
        if not df_gastos.empty:
            fig_gastos = px.pie(
                df_gastos,
                values='total_chf',
                names='categoria',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_gastos.update_layout(title_text="Distribución de Costes")
            st.plotly_chart(fig_gastos, use_container_width=True)
        else:
            st.info("Insuficientes datos de gastos.")

    with c_chart2:
        st.subheader("📈 Evolución de Ventas")
        if not df_ingresos.empty:
            df_ingresos['fecha'] = pd.to_datetime(df_ingresos['fecha'])
            df_trend = df_ingresos.groupby(df_ingresos['fecha'].dt.to_period("M"))['total_final'].sum().reset_index()
            df_trend.rename(columns={'total_final': 'total'}, inplace=True)
            df_trend['fecha'] = df_trend['fecha'].astype(str)
            fig_trend = px.bar(
                df_trend,
                x='fecha',
                y='total',
                labels={'total': 'Facturación (€)', 'fecha': 'Mes'},
                color='total',
                color_continuous_scale='Bluyl'
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Sin histórico de ventas.")

    # 4. AUDITORÍA Y EXPORTACIÓN CONTABLE
    st.subheader("📁 Zona de Auditoría y Contabilidad")
    st.caption("Generación de libros contables digitales para gestoría.")

    col_audit, col_stock = st.columns([2, 1])

    with col_audit:
        hay_datos = (
            not df_gastos.empty
            or not df_ingresos.empty
            or not df_stock.empty
            or not df_flota.empty
        )

        if not hay_datos:
            st.warning("No hay datos para exportar en el Dashboard.")
        else:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                if not df_gastos.empty:
                    df_export_g = df_gastos.copy()
                    if "evidencia_url" in df_export_g.columns:
                        df_export_g["LINK_DOCUMENTO"] = df_export_g["evidencia_url"].apply(
                            lambda x: generar_enlace_temporal(x, db))
                    df_export_g.to_excel(writer, sheet_name='Libro_Gastos', index=False)

                if not df_ingresos.empty:
                    df_ingresos.to_excel(writer, sheet_name='Libro_Ingresos', index=False)

                if not df_stock.empty:
                    df_stock.to_excel(writer, sheet_name='Inventario_Cierre', index=False)

                if not df_flota.empty:
                    df_flota.to_excel(writer, sheet_name='Flota', index=False)

            st.download_button(
                label="📥 Descargar Cierre Contable (Excel + Enlaces)",
                data=buffer.getvalue(),
                file_name=f"Cierre_Contable_{datetime.now().strftime('%Y-%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    with col_stock:
        st.markdown("##### 🔴 Alertas de Stock")
        if not df_stock.empty:
            critico = df_stock[df_stock["stock"] <= df_stock["minimo"]]
            if not critico.empty:
                st.error(f"Hay {len(critico)} referencias bajo mínimos.")
                st.dataframe(critico[["nombre", "stock", "minimo"]], use_container_width=True, hide_index=True)
            else:
                st.success("Inventario saneado. Sin roturas de stock.")