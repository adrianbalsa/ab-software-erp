import streamlit as st


def render_tools_view(db):
    st.title("🛠️ Centro de Utilidades de Ingeniería - AB Software")

    tab1, tab2, tab3 = st.tabs([
        "🚀 Optimizador de Viajes (ROI)",
        "🧮 Calculadora de Obra",
        "📏 Conversor Técnico"
    ])

    # --- TAB 1: OPTIMIZADOR LOGÍSTICO (ROI) ---
    with tab1:
        st.subheader("Análisis de Rentabilidad de Desplazamiento")
        st.write("¿Compensa ir a una tienda lejana por un descuento?")

        col1, col2 = st.columns(2)
        with col1:
            consumo = st.number_input("Consumo Vehículo (L/100km):", value=8.5, step=0.1)
            precio_gas = st.number_input("Precio Combustible (CHF/L):", value=1.82, step=0.01)
            precio_hora = st.number_input("Coste de tu Tiempo (CHF/Hora):", value=80.0, step=5.0)

        with col2:
            km_extra = st.number_input("Km Extra (Ida y Vuelta):", value=20, step=1)
            minutos_extra = st.number_input("Minutos Extra de viaje:", value=30, step=5)
            descuento_total = st.number_input("Descuento total en la compra (CHF):", value=50.0, step=1.0)

        # Lógica de cálculo
        gasto_combustible = (km_extra / 100) * consumo * precio_gas
        gasto_tiempo = (minutos_extra / 60) * precio_hora
        coste_logistico_total = gasto_combustible + gasto_tiempo
        beneficio_final = descuento_total - coste_logistico_total

        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Coste del Desplazamiento", f"{coste_logistico_total:.2f} CHF")

        if beneficio_final > 0:
            st.success(f"✅ **SÍ COMPENSA.** Ahorro real neto: **{beneficio_final:.2f} CHF**")
        else:
            st.error(f"❌ **NO COMPENSA.** Pierdes **{abs(beneficio_final):.2f} CHF** respecto a comprarlo cerca.")

    # --- TAB 2: CALCULADORA DE OBRA (RESTAURADA) ---
    with tab2:
        st.subheader("Cálculo de Materiales (Mortero / Cemento)")
        st.write("Calcula el volumen y peso de material para superficies planas.")

        ca, cb = st.columns(2)
        largo = ca.number_input("Largo de la superficie (m):", min_value=0.0, value=5.0)
        ancho = ca.number_input("Ancho de la superficie (m):", min_value=0.0, value=4.0)
        espesor_cm = cb.number_input("Espesor de la capa (cm):", min_value=0.0, value=3.0)
        densidad = cb.number_input("Densidad material (kg/m³):", value=1800)  # Estándar mortero

        # Cálculos técnicos
        superficie = largo * ancho
        volumen_m3 = superficie * (espesor_cm / 100)
        peso_total_kg = volumen_m3 * densidad
        sacos_25kg = int(peso_total_kg / 25) + 1

        st.divider()
        res1, res2, res3 = st.columns(3)
        res1.metric("Superficie", f"{superficie:.2f} m²")
        res2.metric("Peso Necesario", f"{peso_total_kg:,.1f} kg")
        res3.metric("Sacos (25kg)", f"{sacos_25kg} uds")

        st.info(
            f"💡 Para cubrir {superficie:.2f} m² con un espesor de {espesor_cm} cm, necesitas aproximadamente {sacos_25kg} sacos.")

    # --- TAB 3: CONVERSOR TÉCNICO (RESTAURADO) ---
    with tab3:
        st.subheader("Conversor de Medidas de Precisión")

        col_in, col_res = st.columns(2)
        with col_in:
            valor_conv = st.number_input("Introduce valor a convertir:", value=1.0, step=0.01)
            tipo_conv = st.selectbox("Tipo de conversión:", [
                "Pulgadas ➔ Milímetros",
                "Milímetros ➔ Pulgadas",
                "Pies ➔ Metros",
                "Metros ➔ Pies"
            ])

        with col_res:
            if "Pulgadas ➔ Milímetros" in tipo_conv:
                resultado = valor_conv * 25.4
                st.metric("Resultado", f"{resultado:.2f} mm")
            elif "Milímetros ➔ Pulgadas" in tipo_conv:
                resultado = valor_conv / 25.4
                st.metric("Resultado", f"{resultado:.4f} \"")
            elif "Pies ➔ Metros" in tipo_conv:
                resultado = valor_conv * 0.3048
                st.metric("Resultado", f"{resultado:.3f} m")
            else:
                resultado = valor_conv / 0.3048
                st.metric("Resultado", f"{resultado:.2f} ft")

        st.caption("⚙️ Conversiones basadas en estándares internacionales de construcción.")