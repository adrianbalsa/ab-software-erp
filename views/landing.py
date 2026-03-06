import streamlit as st
import streamlit.components.v1 as components

def render_landing_page():
    # CSS Inyectado para diseño premium (Estilo Holded/SaaS)
    st.markdown("""
        <style>
        .main { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        .hero-section { padding: 4rem 0; text-align: center; }
        .hero-title { font-size: 3.5rem; font-weight: 900; color: #102A43; line-height: 1.2; margin-bottom: 1rem; }
        .hero-subtitle { font-size: 1.25rem; color: #486581; max-width: 800px; margin: 0 auto 2rem auto; }
        .highlight-emerald { color: #27AB83; }
        
        .trust-badge { display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 3rem; color: #829AB1; font-weight: 600; }
        .stars { color: #00B67A; font-size: 1.2rem; } /* Color Trustpilot */
        
        .section-title { font-size: 2.5rem; font-weight: 800; color: #102A43; text-align: center; margin: 4rem 0 2rem 0; }
        
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; padding: 1rem; }
        .feature-card { background: white; padding: 2.5rem; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.03); border: 1px solid #E2E8F0; transition: transform 0.2s; }
        .feature-card:hover { transform: translateY(-5px); border-color: #27AB83; }
        .feature-icon { font-size: 2.5rem; margin-bottom: 1rem; }
        .feature-title { font-size: 1.3rem; font-weight: 700; color: #102A43; margin-bottom: 0.8rem; }
        .feature-text { color: #627D98; line-height: 1.6; }
        
        .pricing-card { background: white; padding: 3rem; border-radius: 16px; text-align: center; border: 1px solid #E2E8F0; }
        .pricing-card.pro { border: 2px solid #27AB83; box-shadow: 0 20px 25px -5px rgba(39, 171, 131, 0.1); position: relative; }
        .badge-pro { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #27AB83; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
        .price { font-size: 3rem; font-weight: 900; color: #102A43; margin: 1rem 0; }
        .price span { font-size: 1rem; color: #829AB1; font-weight: normal; }
        
        .stButton>button { border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem; height: auto; }
        .btn-primary>button { background-color: #27AB83 !important; color: white !important; border: none !important; }
        </style>
    """, unsafe_allow_html=True)

    # --- 1. HERO SECTION ---
    st.markdown("""
        <div class="hero-section">
            <h1 class="hero-title">El Sistema Operativo que<br><span class="highlight-emerald">Acelera tu Logística</span></h1>
            <p class="hero-subtitle">Centraliza tus portes, automatiza la facturación VeriFactu y conecta con tu asesoría en tiempo real. Diseñado para maximizar el flujo de caja de flotas modernas.</p>
        </div>
    """, unsafe_allow_html=True)

    # Botones principales
    col1, col2, col3, col4 = st.columns([1, 1.5, 1.5, 1])
    with col2:
        if st.button("Empieza Gratis 14 días", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
    with col3:
        if st.button("Iniciar Sesión", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()

    # --- 2. SOCIAL PROOF (TRUSTPILOT MOCK) ---
    st.markdown("""
        <div class="trust-badge">
            <span>Excelente</span>
            <span class="stars">★★★★★</span>
            <span>Basado en opiniones verificadas de transportistas</span>
        </div>
    """, unsafe_allow_html=True)
    st.divider()

    # --- 3. CARACTERÍSTICAS PRINCIPALES (Grid) ---
    st.markdown('<h2 class="section-title">Todo lo que necesitas, en un solo lugar</h2>', unsafe_allow_html=True)
    
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">🚚</div>
                <div class="feature-title">Gestión de Portes Inteligente</div>
                <div class="feature-text">Olvida el papel. Registra albaranes y viajes desde el móvil en la cabina del camión. Asigna conductores, vehículos y costes con un clic para tener rentabilidad por viaje en tiempo real.</div>
            </div>
        """, unsafe_allow_html=True)
        st.write("") # Espaciador
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">⚖️</div>
                <div class="feature-title">Facturación VeriFactu Nativa</div>
                <div class="feature-text">Cumple con la Ley Antifraude española desde el día uno. Generación de facturas en PDF con huella digital, conexión directa con la AEAT y control de cobros para reducir la morosidad.</div>
            </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">🤝</div>
                <div class="feature-title">Portal para Asesorías</div>
                <div class="feature-text">Ahorra docenas de horas al trimestre. Tu gestor tiene su propio acceso limitado para descargar facturas de ingresos y gastos, listos para presentar los impuestos. Cero emails.</div>
            </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("""
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Control Financiero y Flota</div>
                <div class="feature-text">Mantenimientos, caducidad de seguros, ITV y control de gastos (combustible, peajes). Un panel de control económico que te muestra dónde ganas y dónde pierdes dinero.</div>
            </div>
        """, unsafe_allow_html=True)

    st.divider()

    # --- 4. SECCIÓN DE PRECIOS ---
    st.markdown('<h2 class="section-title">Planes que escalan con tu flota</h2>', unsafe_allow_html=True)
    
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("""
            <div class="pricing-card">
                <h3>Starter</h3>
                <div class="price">0€<span>/mes</span></div>
                <p style="color: #627D98; margin-bottom: 2rem;">Para autónomos empezando</p>
                <ul style="text-align: left; color: #486581; line-height: 2;">
                    <li>✅ 15 portes al mes</li>
                    <li>✅ Facturación básica</li>
                    <li>❌ Portal de asesoría</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    with p2:
        st.markdown("""
            <div class="pricing-card pro">
                <div class="badge-pro">MÁS POPULAR</div>
                <h3>Pro</h3>
                <div class="price">19€<span>/mes</span></div>
                <p style="color: #627D98; margin-bottom: 2rem;">Para transportistas consolidados</p>
                <ul style="text-align: left; color: #486581; line-height: 2;">
                    <li>✅ Portes ilimitados</li>
                    <li>✅ Facturación VeriFactu</li>
                    <li>✅ Portal de asesoría</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    with p3:
        st.markdown("""
            <div class="pricing-card">
                <h3>Business</h3>
                <div class="price">49€<span>/mes</span></div>
                <p style="color: #627D98; margin-bottom: 2rem;">Para flotas y agencias</p>
                <ul style="text-align: left; color: #486581; line-height: 2;">
                    <li>✅ Todo lo del plan Pro</li>
                    <li>✅ Múltiples usuarios/choferes</li>
                    <li>✅ Control de Flota y RRHH</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><p style='text-align: center; color: #829AB1; font-size: 0.9rem;'>© 2026 AB Logistics OS. Diseñado con estándares bancarios de seguridad.</p>", unsafe_allow_html=True)
