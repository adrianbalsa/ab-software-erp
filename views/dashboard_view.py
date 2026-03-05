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
    st.title("📊 Cuadro de Mando Integral")

    if 'empresaid' not in st.session_state:
        st.error("⚠️ Sesión inválida. Por favor, reinicia el sistema.")
        return

    eid = st.session_state.empresaid
    usuario = st.session_state.username

    # 1. CARGA DE DATOS SINCRONIZADA
    with st.spinner("🔄 Procesando analítica en tiempo real..."):
        try:
            # Datos originales
            t_gastos = db.table("gastos").select("*").eq("empresa_id", eid).execute()
            t_ingresos = db.table("presupuestos").select("*").eq("empresa_id", eid).eq("estado", "Facturado").execute()
            t_flota = db.table("flota").select("*").eq("empresa_id", eid).execute()
            t_stock = db.table("inventario").select("*").eq("empresa_id", eid).execute()
            
            # Nuevos datos: Motor Logístico
            t_facturas = db.table("facturas").select("*").eq("empresa_id", eid).execute()
            t_portes = db.table("portes").select("*").eq("empresa_id", eid).execute()

            df_gastos = pd.DataFrame(t_gastos.data)
            df_ingresos = pd.DataFrame(t_ingresos.data)
            df_flota = pd.DataFrame(t_flota.data)
            df_stock = pd.DataFrame(t_stock.data)
            df_facturas = pd.DataFrame(t_facturas.data) if t_facturas.data else pd.DataFrame()
            df_portes = pd.DataFrame(t_portes.data) if t_portes.data else pd.DataFrame()

        except Exception as e:
            st.error(f"Error de conexión DB: {e}")
            return

    # --- NUEVO: KPIs DE LOGÍSTICA Y FACTURACIÓN ---
    st.markdown("### 🚚 Rendimiento Logístico")
    
    # Cálculos seguros por si las tablas están vacías
    total_facturas_reales = df_facturas["total_factura"].sum() if not df_facturas.empty and "total_factura" in df_facturas.columns else 0.0
    total_viajes = len(df_portes) if not df_portes.empty else 0
    dinero_pendiente = df_portes[df_portes['estado'] == 'pendiente']['precio_pactado'].sum() if not df_portes.empty and 'estado' in df_portes.columns else 0.0

    col_log1, col_log2, col_log3 = st.columns(3)
    col_log1.metric(label="💰 Total Facturado (Año)", value=f"{total_facturas_reales:,.2f} €")
    col_log2.metric(
        label="⏳ Dinero en la calle", 
        value=f"{dinero_pendiente:,.2f} €", 
        delta="Portes pendientes de facturar", 
        delta_color="off"
    )
    col_log3.metric(label="🚚 Viajes Realizados", value=f"{total_viajes}")

    st.divider()

    # --- ORIGINAL: KPIs FINANCIEROS GLOBALES ---
    st.markdown(f"### 💼 Situación Financiera Global: {usuario}")

    total_gastos = df_gastos["total_chf"].sum() if not df_gastos.empty else 0.0
    # Sumamos las facturas reales de portes + presupuestos antiguos facturados para no perder histórico
    total_ventas = total_facturas_reales + (df_ingresos["total_final"].sum() if not df_ingresos.empty else 0.0)
    resultado_neto = total_ventas - total_gastos
    margen_beneficio = (resultado_neto / total_ventas * 100) if total_ventas > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Ingresos Totales", f"{total_ventas:,.2f} €", delta="Logística + Presup.")
    kpi2.metric("Gastos Operativos", f"{total_gastos:,.2f} €", delta="-Salidas", delta_color="inverse")
    kpi3.metric("Resultado Neto (EBIT)", f"{resultado_neto:,.2f} €", delta=f"{margen_beneficio:.1f}% Margen")
    activos_flota = len(df_flota) if not df_flota.empty else 0
    kpi4.metric("Activos en Flota", f"{activos_flota} uds")

    st.divider()

    # --- ORIGINAL: ANÁLISIS VISUAL ---
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
        st.subheader("📈 Evolución de Ventas (Histórico)")
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
            st.info("Sin histórico de presupuestos mensuales.")

    # --- ORIGINAL: AUDITORÍA Y EXPORTACIÓN CONTABLE ---
    st.subheader("📁 Zona de Auditoría y Contabilidad")
    st.caption("Generación de libros contables digitales para gestoría.")

    col_audit, col_stock = st.columns([2, 1])

    with col_audit:
        hay_datos = (
            not df_gastos.empty
            or not df_ingresos.empty
            or not df_stock.empty
            or not df_flota.empty
            or not df_facturas.empty # Añadido control de facturas
        )

        if not hay_datos:
            st.warning("No hay datos para exportar en el Dashboard.")
        else:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Exportamos las nuevas facturas de logística
                if not df_facturas.empty:
                    df_facturas.to_excel(writer, sheet_name='Facturas_Emitidas', index=False)
                    
                if not df_gastos.empty:
                    df_export_g = df_gastos.copy()
                    if "evidencia_url" in df_export_g.columns:
                        df_export_g["LINK_DOCUMENTO"] = df_export_g["evidencia_url"].apply(
                            lambda x: generar_enlace_temporal(x, db))
                    df_export_g.to_excel(writer, sheet_name='Libro_Gastos', index=False)

                if not df_ingresos.empty:
                    df_ingresos.to_excel(writer, sheet_name='Libro_Ingresos_Antiguos', index=False)

                if not df_stock.empty:
                    df_stock.to_excel(writer, sheet_name='Inventario_Cierre', index=False)

                if not df_flota.empty:
                    df_flota.to_excel(writer, sheet_name='Flota', index=False)

            st.download_button(
                label="📥 Descargar Cierre Contable Completo (Excel)",
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