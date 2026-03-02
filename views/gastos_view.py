import streamlit as st
from utils.azure_helper import AzureService
from datetime import date
import time


def render_gastos_view(db):
    # --- 🔒 INICIO DEL CERROJO (PLAN STARTER) ---
    if st.session_state.get('plan', 'starter') == 'starter':
        try:
            # Ahora contamos en la tabla de gastos
            conteo = db.table('gastos').select('id', count='exact').eq('empresa_id', st.session_state.empresa_id).execute()
            total_reg = conteo.count if conteo.count is not None else 0
            
            if total_reg >= 100:
                st.error(f"### 🛑 Límite de Plan Starter alcanzado ({total_reg}/100 gastos)")
                st.warning("No puedes registrar más gastos operativos en el plan gratuito.")
                st.info("👉 **Ve al menú lateral izquierdo y haz clic en 'Upgrade a Pro'** para continuar gestionando tu contabilidad.")
                st.stop() 
        except Exception as e:
            pass
    # --- 🔓 FIN DEL CERROJO ---
    st.title("💸 Gestión y Digitalización de Gastos")

       # Verificación de seguridad
    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid or "username" not in st.session_state:
        st.error("Sesión inválida.")
        return

    usuario_actual = st.session_state.username

    usuario_actual = st.session_state.username  # <--- CAPTURAMOS EL USUARIO

    # Configuración de Entorno
    moneda_base = st.selectbox("Moneda de Registro", ["EUR", "CHF", "USD"], index=0)

    # Layout: Izquierda (Entrada), Derecha (Validación)
    col_input, col_valid = st.columns([1, 1])

    with col_input:
        st.subheader("1. Digitalización (OCR)")
        uploaded_file = st.file_uploader("Subir Ticket o Factura (PDF/JPG)", type=['png', 'jpg', 'jpeg', 'pdf'])

        if uploaded_file:
            st.session_state.temp_ticket = uploaded_file
            st.success("Archivo cargado. Listo para analizar.")

        # Botón IA con fallback
        if st.button("⚡ EXTRAER DATOS CON IA", type="primary") and 'temp_ticket' in st.session_state:
            with st.spinner("Conectando con Azure Intelligence..."):
                datos_ia = AzureService.analizar_ticket(st.session_state.temp_ticket)
                if datos_ia:
                    st.session_state.datos_gastos = datos_ia
                    st.success("✅ Datos extraídos correctamente.")
                else:
                    st.warning("⚠️ No se pudo usar la IA (o faltan claves). Pasa a modo manual.")
                    st.session_state.datos_gastos = {}  # Diccionario vacío para no romper

    with col_valid:
        st.subheader("2. Validación y Contabilización")

        # Recuperamos datos de sesión o vacíos
        defaults = st.session_state.get("datos_gastos", {})

        with st.form("form_gasto_final"):
            c1, c2 = st.columns(2)
            prov = c1.text_input("Proveedor", value=defaults.get("Proveedor", ""))
            fecha = c2.date_input("Fecha Gasto", value=defaults.get("Fecha", date.today()))

            c3, c4 = st.columns(2)
            # Usamos float() para asegurar que si viene 0.0 se muestre bien
            val_total = float(defaults.get("Total_CHF", 0.0))
            total = c3.number_input(f"Importe Total ({moneda_base})", min_value=0.0, value=val_total, step=0.5)
            cat = c4.selectbox("Categoría Contable",
                               ["Materiales", "Combustible", "Dietas", "Hospedaje", "Suministros", "Varios"])

            concepto = st.text_area("Concepto / Descripción", value=defaults.get("Concepto", ""))

            if st.form_submit_button("💾 REGISTRAR GASTO EN LIBRO"):
                if total > 0 and prov:
                    ruta_evidencia = None

                    # Intento de subida de imagen
                    if 'temp_ticket' in st.session_state:
                        try:
                            # Nombre único: ID_EMPRESA / TIMESTAMP_NOMBRE
                            file_obj = st.session_state.temp_ticket
                            file_obj.seek(0)
                            filename = f"{eid}/{int(time.time())}_{file_obj.name}"

                            db.storage.from_("tickets").upload(
                                path=filename,
                                file=file_obj.read(),
                                file_options={"content-type": file_obj.type}
                            )
                            ruta_evidencia = filename
                        except Exception as e:
                            st.error(f"Error subiendo imagen (el gasto se guardará sin foto): {e}")

                    # Insertar en DB
                    try:
                        db.table("gastos").insert({
                            "empresa_id": eid,
                            "empleado": usuario_actual,  # <--- AQUÍ ESTABA EL ERROR (FALTABA ESTE CAMPO)
                            "proveedor": prov,
                            "fecha": str(fecha),
                            "total_chf": total,
                            "categoria": cat,
                            "concepto": concepto,
                            "moneda": moneda_base,
                            "evidencia_url": ruta_evidencia
                        }).execute()

                        st.success("✅ Gasto contabilizado correctamente.")
                        # Limpieza
                        if 'temp_ticket' in st.session_state: del st.session_state.temp_ticket
                        if 'datos_gastos' in st.session_state: del st.session_state.datos_gastos
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error DB: {e}")
                else:
                    st.warning("Debes indicar al menos Proveedor e Importe.")