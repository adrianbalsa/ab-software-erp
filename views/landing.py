import streamlit as st

def render_landing_page():
    # CSS inyectado para estilo premium
    st.markdown("""
        <style>
        .hero-title { font-size: 3rem; font-weight: 800; color: #102A43; text-align: center; }
        .highlight { color: #27AB83; }
        .feature-card { background-color: white; padding: 2rem; border-radius: 15px; border-top: 5px solid #27AB83; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .roi-box { background-color: #102A43; color: white; padding: 2rem; border-radius: 15px; text-align: center; }
        .roi-number { font-size: 2.5rem; font-weight: bold; color: #27AB83; }
        </style>
    """, unsafe_allow_html=True)

    # 1. HERO SECTION
    st.markdown('<h1 class="hero-title">Gestiona tu logística como un <span class="highlight">experto</span></h1>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #486581;'>El ERP diseñado por economistas para transportistas. Facturación VeriFactu en 1 clic.</p>", unsafe_allow_html=True)
    
    col_space1, col_btn, col_space2 = st.columns([1,1,1])
    with col_btn:
        if st.button("🚀 ACCESO CLIENTES", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    st.divider()

    # 2. LOS 3 PILARES
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="feature-card"><h3>📦 Gestión de Portes</h3><p>Registra albaranes en 5 segundos. Cero papeles.</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="feature-card"><h3>⚖️ VeriFactu Ready</h3><p>Facturas legales. Tranquilidad total ante Hacienda.</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="feature-card"><h3>🤝 Nodo Asesoría</h3><p>Tu gestor descarga todo con un clic. Eficiencia total.</p></div>', unsafe_allow_html=True)

    st.divider()

    # 3. CALCULADORA DE ROI (La joya de la corona)
    st.subheader("📊 Calculadora de Ahorro Mensual")
    st.write("Descubre cuánto dinero pierdes haciendo facturas a mano o en Excel.")
    
    col_input, col_result = st.columns([1, 1])
    
    with col_input:
        viajes_mes = st.slider("¿Cuántos portes/viajes realizas al mes?", min_value=10, max_value=500, value=50, step=10)
        coste_hora = st.number_input("¿Cuánto valoras tu hora de trabajo o la de tu administrativo? (€/h)", min_value=10, value=15)
        
    with col_result:
        # Lógica económica: Hacer una factura en excel = 15 mins. En AB OS = 1 min. Ahorro = 14 mins por viaje.
        minutos_ahorrados = viajes_mes * 14
        horas_ahorradas = minutos_ahorrados / 60
        dinero_ahorrado = horas_ahorradas * coste_hora
        
        st.markdown(f"""
            <div class="roi-box">
                <p>Con AB Logistics OS ahorrarás:</p>
                <div class="roi-number">{int(horas_ahorradas)} horas/mes</div>
                <div class="roi-number">+{int(dinero_ahorrado)} €/mes</div>
                <p style="font-size: 0.9rem; margin-top: 10px; color: #cbd5e1;">Tu suscripción se paga sola con los primeros 5 portes.</p>
            </div>
        """, unsafe_allow_html=True)
