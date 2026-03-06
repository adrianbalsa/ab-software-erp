import streamlit as st

def render_privacy_policy():
    st.title("Política de Privacidad")
    st.write("""
    **1. Responsable del Tratamiento:** Adrián Balsa (AB Logistics OS).  
    **2. Datos que recogemos:** Correo electrónico, datos de facturación y datos operativos de transporte.  
    **3. Finalidad:** Proveer el servicio de ERP y soporte técnico.  
    **4. Conservación:** Los datos se conservarán mientras se mantenga la relación comercial o durante los años necesarios para cumplir con obligaciones legales (AEAT).
    """)

def render_terms_conditions():
    st.title("Términos y Condiciones")
    st.write("""
    **Suscripciones:** Los planes se facturan por adelantado cada 30 días.  
    **Cancelación:** El usuario puede cancelar en cualquier momento desde su panel, manteniendo el acceso hasta el final del periodo pagado.  
    **Ley Aplicable:** Estas condiciones se rigen por la ley española.
    """)