import streamlit as st
from PIL import Image
from supabase import create_client
import time
import stripe
from dotenv import load_dotenv
import os

# 1. PAGE CONFIG SIEMPRE DEBE SER EL PRIMER COMANDO STREAMLIT
st.set_page_config(page_title='AB Logistics OS', page_icon='📊', layout='wide')

# IMPORTACIONES CORREGIDAS (Añadido el prefijo scanner a todo)
from scanner.services.auth_service import AuthService
from scanner.views.landing import render_landing_page

load_dotenv()

# Inicializa Stripe
try:
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY') or st.secrets.get('STRIPE_SECRET_KEY', "")
except Exception:
    pass 

# CSS Global
st.markdown('''
    <style>
        [data-testid=stSidebar] { min-width: 260px !important; max-width: 260px !important; }
        [data-testid=stSidebar] .stRadio div { gap: 0.3rem !important; }
        [data-testid=stSidebar] .stRadio label { font-size: 15px !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        [data-testid=stSidebar] img { border-radius: 10px; margin-bottom: 1rem; }
    </style>
''', unsafe_allow_html=True)

# Inicializar Base de Datos
from scanner.services.db_context import DBContext
try:
    if 'SUPABASE_URL' in st.secrets and 'SUPABASE_KEY' in st.secrets:
        db_admin = create_client(
            st.secrets['SUPABASE_URL'],
            st.secrets.get('SUPABASE_SERVICE_KEY', st.secrets['SUPABASE_KEY'])
        )
        db = DBContext(db_admin)
    else:
        st.error('Faltan secretos: SUPABASE_URL / SUPABASE_KEY.')
        st.stop()
except Exception as e:
    st.error(f'Error critico conectando a Supabase: {e}')
    st.stop()

# Funciones Stripe
def crear_checkout_session(price_id, empresa_id):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url='http://localhost:8501/?pago=exito', 
            cancel_url='http://localhost:8501/?pago=cancelado',
            client_reference_id=empresa_id 
        )
        return session.url
    except Exception as e:
        st.error(f"Error conectando con el banco: {e}")
        return None

def mostrar_ui_suscripcion(plan_actual, empresa_id):
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏢 Mi Suscripción")
    PRICE_PRO = "price_1T6tvXEnVY2TFI6OKL0Iu5gd"
    PRICE_BUSINESS = "price_1T6twbEnVY2TFI6O2DUCRJen"

    if plan_actual == 'starter' or not plan_actual:
        st.sidebar.warning("Plan actual: **Starter**")
        if st.sidebar.button("🚀 Upgrade a Pro (19€/mes)"):
            url = crear_checkout_session(PRICE_PRO, empresa_id)
            if url: st.sidebar.markdown(f"[💳 Haz clic aquí para pagar]({url})")
        if st.sidebar.button("💼 Upgrade a Business (49€/mes)"):
            url = crear_checkout_session(PRICE_BUSINESS, empresa_id)
            if url: st.sidebar.markdown(f"[💳 Haz clic aquí para pagar]({url})")
    elif plan_actual == 'pro':
        st.sidebar.success("Plan actual: **Pro**")
    elif plan_actual == 'business':
        st.sidebar.success("Plan actual: **Business**")

# Vistas Globales Corregidas
from scanner.views.dashboard_view import render_dashboard
from scanner.views.gastos_view import render_gastos_view
from scanner.views.inventory_view import render_inventory_view
from scanner.views.flota_view import render_flota_view
from scanner.views.rrhh_view import render_rrhh_view
from scanner.views.presupuestos_view import render_presupuestos_view
from scanner.views.eco_view import render_eco_view

def main():
    # --- 1. HANDLER DE PAGOS STRIPE ---
    if st.query_params.get('pago') == 'exito':
        st.balloons()
        st.success("🎉 ¡Pago confirmado!")
        st.query_params.clear()

    elif st.query_params.get('pago') == 'cancelado':
        st.warning("❌ Pago cancelado.")
        st.query_params.clear()

    # --- 2. VERIFICACIÓN PÚBLICA (Ruta Corregida) ---
    if 'num' in st.query_params and 'hash' in st.query_params:
        from scanner.views.verify_public import render_verify_public
        render_verify_public(db)
        return

    # --- 3. GESTIÓN DE SESIÓN Y LANDING PAGE ---
    if 'loggedin' not in st.session_state:
        st.session_state.loggedin = False
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False

    if not st.session_state.loggedin:
        if st.session_state.show_login:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                try:
                    logo = Image.open("assets/logo.png")
                    st.image(logo, use_container_width=True)
                except:
                    st.title("AB Logistics OS")

                st.markdown('### Acceso al Sistema')
                with st.form('login_master'):
                    u = st.text_input('Usuario (Email)', placeholder='admin@empresa.com')
                    p = st.text_input('Contraseña', type='password')
                    submitted = st.form_submit_button('ENTRAR', use_container_width=True)

                if submitted:
                    try:
                        auth = AuthService(db_admin)
                        res = auth.login(u, p)
                        if res['success']:
                            empresa_id = res['user']['empresa_id']
                            st.session_state.loggedin = True
                            st.session_state.username = u
                            st.session_state.empresa_id = empresa_id
                            st.session_state.rol = res['user'].get('rol', 'user')
                            
                            try:
                                emp_data = db_admin.table('empresas').select('plan, estado_pago').eq('id', empresa_id).execute()
                                if emp_data.data:
                                    st.session_state.plan = emp_data.data[0].get('plan') or 'starter'
                                    st.session_state.estado_pago = emp_data.data[0].get('estado_pago') or 'activo'
                            except Exception:
                                st.session_state.plan = 'starter'
                                st.session_state.estado_pago = 'activo'
                            st.rerun()
                        else:
                            st.error('Credenciales inválidas')
                    except Exception as e:
                        st.error(f'Error de autenticación: {e}')
                
                if st.button("← Volver a Inicio"):
                    st.session_state.show_login = False
                    st.rerun()
        else:
            render_landing_page()
            
        return

    # --- 4. VERIFICACIÓN DE IMPAGOS ---
    if st.session_state.get('estado_pago') == 'impago':
        st.error("### 🛑 Cuenta Suspendida")
        st.warning("No hemos podido procesar el cobro de tu suscripción.")
        st.link_button("💳 Gestionar Pago en Stripe", "https://billing.stripe.com/p/login/test_dRm28r8M1emrd9PbZucEw00")
        if st.button("Cerrar Sesión"):
            st.session_state.loggedin = False
            st.rerun()
        st.stop()

    # --- 5. SIDEBAR Y MENÚ DEL ERP ---
    with st.sidebar:
        try:
            st.image('assets/logo.png', use_container_width=True)
        except Exception:
            st.markdown('### AB Software')

        st.markdown(f'**Usuario:** {st.session_state.username}')
        mostrar_ui_suscripcion(st.session_state.get('plan', 'starter'), st.session_state.empresa_id)

        if st.session_state.get('rol') == 'admin':
            opciones = ['Dashboard', 'Portes', 'Facturas', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad', 'Admin']
        else:
            opciones = ['Dashboard', 'Portes', 'Facturas', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad']

        menu = st.radio('NAVEGACIÓN', opciones, label_visibility='collapsed')
        
        st.markdown('---')
        if st.button('CERRAR SESIÓN', use_container_width=True):
            st.session_state.loggedin = False
            st.session_state.show_login = False 
            st.rerun()

    # --- 6. RENDERIZADO DE VISTAS (Rutas Corregidas) ---
    try:
        if menu == 'Dashboard': render_dashboard(db)
        elif menu == 'Portes': 
            from scanner.views.portes_view import render_portes_view
            render_portes_view(db)
        elif menu == "Facturas": 
            from scanner.views.facturas_view import render_facturas_view
            render_facturas_view(db)
        elif menu == 'Gastos': render_gastos_view(db)
        elif menu == 'Presupuestos': render_presupuestos_view(db)
        elif menu == 'Inventario': render_inventory_view(db)
        elif menu == 'Flota': render_flota_view(db)
        elif menu == 'RRHH': render_rrhh_view(db)
        elif menu == 'Sostenibilidad': render_eco_view(db)
        elif menu == 'Admin': 
            from scanner.views.superadmin_view import render_superadmin_view
            render_superadmin_view(db)
    except Exception as e:
        st.error(f'Error cargando el módulo {menu}: {e}')

if __name__ == '__main__':
    main()