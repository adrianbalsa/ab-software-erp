import streamlit as st
import pandas as pd

def render_landing_page():
    # --- 1. MOTOR CSS: HACKEANDO STREAMLIT PARA PARECER HOLDED ---
    st.markdown("""
        <style>
        /* Importar fuente moderna tipo SaaS */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            scroll-behavior: smooth;
        }

        /* Ocultar elementos sobrantes de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Ajuste de márgenes globales de Streamlit */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 0rem !important;
            max-width: 1200px !important;
        }

        /* --- CLASES PERSONALIZADAS --- */
        .navbar {
            display: flex; justify-content: space-between; align-items: center;
            padding: 1rem 0; border-bottom: 1px solid #E5E7EB; margin-bottom: 3rem;
        }
        .logo-text { font-size: 1.5rem; font-weight: 800; color: #111827; letter-spacing: -1px; }
        
        .hero-section {
            text-align: center; padding: 4rem 1rem;
            background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%);
            border-radius: 20px; margin-bottom: 4rem;
        }
        .hero-title { 
            font-size: 4rem; font-weight: 800; color: #111827; 
            line-height: 1.1; margin-bottom: 1.5rem; letter-spacing: -2px;
        }
        .hero-title span { color: #2563EB; } /* Azul corporativo */
        .hero-subtitle { 
            font-size: 1.25rem; color: #4B5563; max-width: 700px; 
            margin: 0 auto 2.5rem auto; line-height: 1.6;
        }

        /* Grid de Features estilo SaaS */
        .features-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem; margin: 4rem 0;
        }
        .feature-card {
            background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 16px;
            padding: 2.5rem 2rem; transition: all 0.3s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }
        .feature-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            border-color: #2563EB;
        }
        .feature-icon { font-size: 2.5rem; margin-bottom: 1.5rem; }
        .feature-title { font-size: 1.25rem; font-weight: 600; color: #111827; margin-bottom: 0.75rem; }
        .feature-desc { color: #6B7280; line-height: 1.5; font-size: 0.95rem;}

        /* Sección Trust (Logos ficticios o texto) */
        .trust-section {
            text-align: center; padding: 3rem 0; border-top: 1px solid #E5E7EB;
            color: #6B7280; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;
        }
        
        /* Footer */
        .modern-footer {
            margin-top: 5rem; padding: 3rem 0; border-top: 1px solid #E5E7EB;
            text-align: center; color: #6B7280; font-size: 0.875rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- 2. NAVEGACIÓN SUPERIOR (NAVBAR) ---
    st.markdown("""
        <div class="navbar">
            <div class="logo-text">AB Logistics OS.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- 3. SECCIÓN HERO ---
    st.markdown("""
        <div class="hero-section">
            <div class="hero-title">Gestiona tu flota.<br><span>Protege tu margen.</span></div>
            <div class="hero-subtitle">
                El ERP financiero diseñado para transportistas. Automatiza la facturación VeriFactu, 
                controla los costes por kilómetro y deja que los chóferes suban sus albaranes desde el móvil.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Botones de llamada a la acción (CTA) usando Streamlit nativo para lógica
    col_cta1, col_cta2, col_cta3 = st.columns([1, 1.5, 1.5, 1])
    with col_cta2:
        if st.button("Comenzar Prueba Gratuita →", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
    with col_cta3:
        st.link_button("Contactar Ventas", "mailto:ventas@ablogistics-os.com", use_container_width=True)

    st.markdown('<div class="trust-section">Diseñado bajo la nueva Ley Antifraude y Facturación Española 2026</div>', unsafe_allow_html=True)

    # --- 4. HERRAMIENTA DE CAPTACIÓN: CALCULADORA ROI ---
    st.markdown("<br><br><h2 style='text-align: center; font-weight: 800; color: #111827;'>Prueba nuestro motor de rentabilidad.</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6B7280; margin-bottom: 2rem;'>Calcula el beneficio real de tu próximo viaje antes de arrancar el motor.</p>", unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tarifa = st.number_input("Ingreso del Viaje (€)", value=850.0, step=50.0)
            km = st.number_input("Kilómetros totales", value=600, step=10)
        with c2:
            precio_gasoil = st.number_input("Precio Diésel (€/L)", value=1.42, step=0.01)
            litros_100 = st.number_input("Consumo (L/100km)", value=32.0, step=1.0)
        with c3:
            peajes = st.number_input("Peajes / Dietas (€)", value=65.0, step=5.0)
            coste_fijo_km = st.number_input("Coste Amortización/Km", value=0.15, step=0.01)

        coste_combustible = (km / 100) * litros_100 * precio_gasoil
        coste_total = coste_combustible + (km * coste_fijo_km) + peajes
        beneficio = tarifa - coste_total
        margen = (beneficio / tarifa) * 100 if tarifa > 0 else 0

        st.markdown("---")
        res1, res2, res3 = st.columns(3)
        res1.metric("Coste Operativo Real", f"{coste_total:.2f} €")
        
        if beneficio > 0:
            res2.metric("Beneficio Neto", f"{beneficio:.2f} €", f"Margen: {margen:.1f}%")
        else:
            res2.metric("Pérdida Neta", f"{beneficio:.2f} €", "No rentable", delta_color="inverse")
            st.error("⚠️ Este viaje no cubre los costes fijos de amortización del camión. Rechazar o renegociar.")

    # --- 5. GRID DE FUNCIONALIDADES (TRANSICIONES Y HOVER) ---
    st.markdown("""
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">⚖️</div>
                <div class="feature-title">Certificación VeriFactu</div>
                <div class="feature-desc">Emisión de facturas con hash encadenado y código QR. Cumple la Ley Antifraude de la Agencia Tributaria automáticamente, sin miedo a sanciones.</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📱</div>
                <div class="feature-title">Portal del Conductor</div>
                <div class="feature-desc">Tus chóferes no necesitan instalar nada. Escanean un QR y suben fotos de tickets de gasoil y albaranes firmados (CMR) que llegan directo al ERP.</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Dashboard de EBITDA</div>
                <div class="feature-desc">Métricas en tiempo real. Descubre qué rutas son más rentables, controla el gasto en combustible y visualiza tus impuestos trimestrales.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- 6. FOOTER ---
    st.markdown("""
        <div class="modern-footer">
            <p><b>AB Logistics OS</b> - Inteligencia Financiera para el Transporte</p>
            <p>A Coruña, Galicia · <a href="mailto:info@ablogistics-os.com" style="color: #2563EB; text-decoration: none;">Contacto Comercial</a></p>
            <p style="margin-top: 1rem; font-size: 0.75rem;">© 2026 Todos los derechos reservados. Cumplimiento RGPD y LOPD garantizado.</p>
        </div>
    """, unsafe_allow_html=True)