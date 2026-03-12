import streamlit as st
import pandas as pd
from views.portes_view import generar_pdf_portes

def render_facturas_view(db):
    st.title("📑 Historial de Facturación")
    st.markdown("Consulta tus facturas emitidas y recupera los PDFs al instante.")

    try:
        # Traemos todas las facturas de la empresa
        res_facturas = db.table('facturas').select('*').eq('empresa_id', st.session_state.empresa_id).order('fecha_emision', desc=True).execute()

        if res_facturas.data:
            df = pd.DataFrame(res_facturas.data)

            # Buscamos los nombres de los clientes para que la tabla sea legible
            try:
                res_clientes = db.table('clientes').select('id, nombre').eq('empresa_id', st.session_state.empresa_id).execute()
                if res_clientes.data:
                    dict_clientes = {str(c['id']): c['nombre'] for c in res_clientes.data}
                    # Mapeamos el ID al nombre real
                    df['Nombre Cliente'] = df['cliente'].astype(str).map(dict_clientes).fillna(df['cliente'])
                else:
                    df['Nombre Cliente'] = df['cliente']
            except:
                df['Nombre Cliente'] = df['cliente']

            # Formateamos la tabla principal
            df_display = df[['numero_factura', 'Nombre Cliente', 'total_factura', 'fecha_emision']]
            df_display.columns = ['Nº Factura', 'Cliente', 'Total (€)', 'Fecha']

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # --- SECTOR DE DESCARGA ---
            st.divider()
            st.subheader("📥 Recuperar Documento")
            
            # Selector para elegir la factura
            fact_num = st.selectbox("Selecciona una factura para descargar:", df['numero_factura'].tolist())

            # Aislamos los datos de esa factura específica
            fact_data = df[df['numero_factura'] == fact_num].iloc[0]

            # Buscamos los portes que pertenecen a este ID de factura
            res_p = db.table('portes').select('*').eq('factura_id', str(fact_data['id'])).execute()
            df_p = pd.DataFrame(res_p.data)

            if not df_p.empty:
                # Preparamos los portes para el inyector del PDF
                df_p_pdf = df_p[['fecha', 'origen', 'destino', 'descripcion', 'precio_pactado']]
                df_p_pdf.columns = ['Fecha', 'Origen', 'Destino', 'Mercancía', 'Importe (€)']

                # Regeneramos el PDF en memoria
                pdf_bytes = generar_pdf_portes(
                    fact_num,
                    fact_data['Nombre Cliente'],
                    df_p_pdf,
                    fact_data['base_imponible'],
                    fact_data['cuota_iva'],
                    fact_data['total_factura']
                )

                st.download_button(
                    label=f"⬇️ Descargar {fact_num} (PDF)",
                    data=pdf_bytes,
                    file_name=f"{fact_num}_{fact_data['Nombre Cliente'].replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            else:
                st.warning("No se encontraron los portes detallados de esta factura.")
        else:
            # --- NUEVO: ESTADO VACÍO ELEGANTE ---
            st.info("🧾 Aún no tienes facturas registradas en el sistema.")
            st.markdown("""
                **Empieza a facturar bajo la normativa VeriFactu:**
                Ve al módulo de **Portes** para emitir tu primera factura por lotes. 
                Todos los documentos generados estarán preparados para el cumplimiento normativo de 2026.
            """)

    except Exception as e:
        st.error(f"Error cargando el historial: {e}")