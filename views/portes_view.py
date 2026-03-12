import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF
import io

def generar_pdf_portes(num_factura, cliente_nombre, portes_df, base, iva, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabecera
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "FACTURA DE TRANSPORTE", ln=True, align="C")
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, f"Número: {num_factura}", ln=True)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, f"Cliente / Cargador: {cliente_nombre}", ln=True)
    pdf.ln(5)
    
    # Encabezados de la tabla
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 8, "Fecha", border=1, fill=True)
    pdf.cell(40, 8, "Origen", border=1, fill=True)
    pdf.cell(40, 8, "Destino", border=1, fill=True)
    pdf.cell(55, 8, "Mercancía", border=1, fill=True)
    pdf.cell(30, 8, "Importe", border=1, ln=True, fill=True, align="R")
    
    # Filas de datos (Portes)
    pdf.set_font("helvetica", "", 9)
    for _, row in portes_df.iterrows():
        pdf.cell(25, 8, str(row['Fecha']), border=1)
        pdf.cell(40, 8, str(row['Origen'])[:20], border=1) # Truncamos texto largo
        pdf.cell(40, 8, str(row['Destino'])[:20], border=1)
        pdf.cell(55, 8, str(row['Mercancía'])[:30], border=1)
        pdf.cell(30, 8, f"{row['Importe (€)']:.2f} EUR", border=1, ln=True, align="R")
        
    # Totales
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(160, 8, "Base Imponible:", border=0, align="R")
    pdf.cell(30, 8, f"{base:.2f} EUR", border=0, ln=True, align="R")
    
    pdf.cell(160, 8, "IVA (21%):", border=0, align="R")
    pdf.cell(30, 8, f"{iva:.2f} EUR", border=0, ln=True, align="R")
    
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(160, 10, "TOTAL FACTURA:", border=0, align="R")
    pdf.cell(30, 10, f"{total:.2f} EUR", border=0, ln=True, align="R")
    
    # En fpdf2, output() sin argumentos y convertido a bytes sirve para Streamlit
    return bytes(pdf.output())
def render_portes_view(db):
    st.title("🚚 Gestión de Portes y Albaranes")
    st.markdown("Registra tus viajes diarios. A final de mes, podrás facturarlos en bloque.")

    # --- 🔒 CERROJO STARTER ---
    if st.session_state.get('plan', 'starter') == 'starter':
        try:
            conteo = db.table('portes').select('id', count='exact').eq('empresa_id', st.session_state.empresa_id).execute()
            total_reg = conteo.count if conteo.count is not None else 0
            if total_reg >= 30: # Límite de 30 portes para la versión gratuita
                st.error(f"### 🛑 Límite Starter alcanzado ({total_reg}/30 portes)")
                st.info("Para registrar viajes ilimitados y generar facturas automáticas, pásate al Plan Pro en el menú lateral.")
                st.stop()
        except Exception:
            pass
    # --- 🔓 FIN CERROJO ---

    tabs = st.tabs(["📋 Viajes Pendientes", "➕ Añadir Nuevo Porte"])

    # ==========================================
    # PESTAÑA 2: FORMULARIO DE ALTA CON CLIENTE RÁPIDO
    # ==========================================
    with tabs[1]:
        st.subheader("Registrar nuevo servicio")
        
        # 1. Recuperar clientes de la DB
        try:
            res_clientes = db.table('clientes').select('id, nombre').eq('empresa_id', st.session_state.empresa_id).execute()
            lista_clientes = res_clientes.data if res_clientes.data else []
            opciones_clientes = {c['nombre']: c['id'] for c in lista_clientes}
        except:
            opciones_clientes = {}

        # --- ➕ SECCIÓN CLIENTE RÁPIDO ---
        with st.expander("➕ ¿No encuentras el cliente? Añádelo rápido aquí"):
            nuevo_cliente_nom = st.text_input("Nombre del nuevo Cliente/Cargador")
            if st.button("Crear Cliente"):
                if nuevo_cliente_nom:
                    try:
                        db.table('clientes').insert({
                            "nombre": nuevo_cliente_nom, 
                            "empresa_id": st.session_state.empresa_id
                        }).execute()
                        st.success(f"Cliente '{nuevo_cliente_nom}' creado. Ya puedes seleccionarlo abajo.")
                        st.rerun() # Recarga para que aparezca en el desplegable
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe un nombre")

        # --- 🚚 FORMULARIO DE PORTE ---
        with st.form("form_nuevo_porte"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Si hay clientes, mostramos el desplegable
                if opciones_clientes:
                    cliente_seleccionado = st.selectbox("Seleccionar Cliente", options=list(opciones_clientes.keys()))
                    cliente_id = opciones_clientes[cliente_seleccionado]
                else:
                    st.error("⚠️ Crea un cliente arriba primero.")
                    cliente_id = None
                    
                origen = st.text_input("Origen", placeholder="Ej: Puerto de Valencia")
                destino = st.text_input("Destino", placeholder="Ej: Polígono Ind. Getafe")
                descripcion = st.text_input("Mercancía", placeholder="Ej: Bobinas de acero")

            with col2:
                fecha = st.date_input("Fecha de servicio", value=date.today())
                km = st.number_input("Kilómetros", min_value=0.0, step=1.0)
                bultos = st.number_input("Bultos", min_value=1, step=1)
                precio = st.number_input("Precio Pactado (€)", min_value=0.0, step=10.0)

            submit = st.form_submit_button("💾 GUARDAR PORTE", type="primary", use_container_width=True)

            if submit:
                if not cliente_id:
                    st.error("Debes seleccionar o crear un cliente primero para poder asignarle el cobro.")
                elif not origen or not destino or precio <= 0:
                    st.error("Origen, Destino y Precio son obligatorios.")
                else:
                    try:
                        nuevo_porte = {
                            "empresa_id": st.session_state.empresa_id,
                            "cliente_id": cliente_id,
                            "fecha": fecha.isoformat(),
                            "origen": origen,
                            "destino": destino,
                            "km_estimados": km,
                            "bultos": bultos,
                            "descripcion": descripcion,
                            "precio_pactado": precio,
                            "estado": "pendiente"
                        }
                        db.table('portes').insert(nuevo_porte).execute()
                        st.success("✅ Porte guardado correctamente.")
                        st.rerun() # Limpia el formulario enviando los datos
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ==========================================
# ==========================================
    # PESTAÑA 1: LISTADO Y FACTURACIÓN POR LOTES
    # ==========================================
    with tabs[0]:
        st.subheader("Viajes pendientes de facturar")
        try:
            # Traemos los portes pendientes HACIENDO JOIN con la tabla clientes para tener el nombre
            res_portes = db.table('portes').select('id, fecha, origen, destino, descripcion, precio_pactado, clientes(nombre)').eq('empresa_id', st.session_state.empresa_id).eq('estado', 'pendiente').order('fecha', desc=False).execute()
            
            if res_portes.data:
                df_portes = pd.DataFrame(res_portes.data)
                
                # Extraemos el nombre del cliente de forma segura
                df_portes['Cliente'] = df_portes['clientes'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'Desconocido')
                
                # Agrupamos: ¿A quién le queremos facturar hoy?
                clientes_pendientes = df_portes['Cliente'].unique()
                cliente_a_facturar = st.selectbox("🎯 Selecciona el cliente a facturar:", clientes_pendientes)
                
                # Filtramos los viajes solo de ese cliente
                df_cliente = df_portes[df_portes['Cliente'] == cliente_a_facturar]
                portes_ids = df_cliente['id'].tolist() # Guardamos los IDs para actualizarlos luego
                
                # Preparamos la tabla para mostrar
                df_mostrar = df_cliente[['fecha', 'origen', 'destino', 'descripcion', 'precio_pactado']]
                df_mostrar.columns = ['Fecha', 'Origen', 'Destino', 'Mercancía', 'Importe (€)']
                
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                
                # Matemáticas financieras
                base_imponible = df_cliente['precio_pactado'].sum()
                cuota_iva = base_imponible * 0.21
                total_factura = base_imponible + cuota_iva
                
             st.info(f"📊 **Base Imponible:** {base_imponible:.2f} € | **IVA (21%):** {cuota_iva:.2f} € | **TOTAL FACTURA:** {total_factura:.2f} €")
                
                # --- NUEVO: BOTÓN DE EXPORTACIÓN ---
                st.markdown("---") 
                csv = df_cliente.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label=f"📥 Descargar Portes en Excel",
                    data=csv,
                    file_name=f'portes_{cliente_a_facturar.replace(" ", "_")}.csv',
                    mime='text/csv',
                    use_container_width=True 
                )
                # --- LA MAGIA DEL 1-CLIC ---
                if st.button(f"🧾 Emitir Factura por {len(df_cliente)} viajes ({total_factura:.2f} €)", type="primary"):
                    num_fact = f"FAC-{int(date.today().strftime('%Y%m%d'))}-{str(len(portes_ids))[:4]}"
                    
                    try:
                        # 1. Creamos la factura en la BBDD                        
                        nueva_factura = {
                            "empresa_id": st.session_state.empresa_id,
                            "cliente": opciones_clientes[cliente_a_facturar], # 👈 ESTE ES EL DATO QUE EXIGÍA LA BBDD
                            "numero_factura": num_fact,
                            "total_factura": total_factura,
                            "base_imponible": base_imponible,
                            "cuota_iva": cuota_iva,
                            "fecha_emision": date.today().isoformat()
                        }
                        res_fact = db.table('facturas').insert(nueva_factura).execute()
                        factura_id = res_fact.data[0]['id']
                        
                        # 2. Marcamos todos esos portes como 'facturado' y los vinculamos
                        for p_id in portes_ids:
                            db.table('portes').update({"estado": "facturado", "factura_id": factura_id}).eq('id', p_id).execute()
                            
                        # 3. Generamos el PDF en memoria
                        pdf_bytes = generar_pdf_portes(num_fact, cliente_a_facturar, df_mostrar, base_imponible, cuota_iva, total_factura)
                        
                        st.success("✅ ¡Factura generada y viajes archivados!")
                        st.balloons()
                        
                        # 4. Botón de Descarga del PDF
                        st.download_button(
                            label="📥 Descargar Factura (PDF)",
                            data=pdf_bytes,
                            file_name=f"{num_fact}_{cliente_a_facturar.replace(' ', '_')}.pdf",
                            mime="application/pdf"
                        )
                        
                    except Exception as e:
                        st.error(f"Error procesando la facturación: {e}")
                        
            else:
                st.success("🎉 ¡No hay viajes pendientes! Todo está facturado al día.")
                
        except Exception as e:
            st.error(f"Error cargando los datos: {e}")