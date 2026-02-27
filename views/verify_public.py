import streamlit as st


def render_verify_public(db):
    """
    Página pública de verificación Verifactu (sin login).
    CORRECCIONES:
    - Eliminado st.set_page_config (ya llamado en main.py, no puede llamarse dos veces)
    - Corregido: if not res.data  (estaba truncado: "if not res.")
    - Recibe db como parámetro para evitar doble conexión
    """
    st.title("🔍 Verificación de Factura Verifactu")
    st.caption("Sistema de Autenticidad Fiscal - Real Decreto-ley 4/2023")
    st.divider()

    query_params = st.query_params
    num_factura = query_params.get("num", "")
    hash_recibido = query_params.get("hash", "")

    if not num_factura or not hash_recibido:
        st.warning("⚠️ URL incompleta. Escanea el código QR de tu factura.")
        st.info("**Formato esperado**: `?num=FAC-2026-000001&hash=abc123...`")
        return

    with st.spinner("🔎 Verificando autenticidad..."):
        try:
            res = db.table("presupuestos").select(
                "num_factura, fecha_factura, cliente, nif_cliente, "
                "total_final, moneda, hash_factura, numero_secuencial"
            ).eq("num_factura", num_factura).execute()

            # CORRECCIÓN: era "if not res." (incompleto → SyntaxError en producción)
            if not res.data:
                st.error("❌ **FACTURA NO ENCONTRADA**")
                st.warning(f"El número `{num_factura}` no existe en el sistema.")
                return

            factura = res.data[0]
            hash_real = factura.get("hash_factura", "")

            if hash_real == hash_recibido:
                st.success("✅ **FACTURA VÁLIDA Y AUTÉNTICA**")
                st.info("Este documento es **legítimo** y no ha sido alterado.")

                st.markdown("### 📋 Datos de la Factura")
                col1, col2 = st.columns(2)
                col1.metric("📄 Número", num_factura)
                col2.metric("📅 Fecha Emisión", factura.get("fecha_factura", "N/A"))
                col1.metric("🏢 Cliente", factura.get("cliente", "N/A"))
                col2.metric("🆔 NIF Cliente", factura.get("nif_cliente", "N/A"))
                col1.metric(
                    "💰 Total Facturado",
                    f"{factura.get('total_final', 0):.2f} {factura.get('moneda', 'EUR')}"
                )
                col2.metric("🔢 Nº Secuencial", factura.get("numero_secuencial", "N/A"))

                with st.expander("🔒 Ver Hash Completo (SHA-256)"):
                    st.code(hash_real, language="text")
                    st.caption("Este hash criptográfico garantiza que la factura no ha sido modificada.")
            else:
                st.error("❌ **HASH INVÁLIDO - POSIBLE FALSIFICACIÓN**")
                st.warning("⚠️ El hash recibido NO coincide con el registrado en el sistema.")
                st.markdown(f"""
                **Detalles del problema**:
                - Hash esperado: `{hash_real[:32]}...`
                - Hash recibido: `{hash_recibido[:32]}...`

                🚨 **Acción recomendada**: Contacta al emisor de la factura inmediatamente.
                """)

        except Exception as e:
            st.error(f"❌ Error técnico durante la verificación: {e}")

    st.divider()
    st.caption("🔐 Sistema Verifactu - Cumplimiento RD-ley 4/2023 | Certificación de Integridad Fiscal")