import streamlit as st
from supabase import create_client
from services.auth_service import AuthService
import time
import stripe
from dotenv import load_dotenv
import os

load_dotenv()
# Inicializa Stripe con tu clave secreta
stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def crear_checkout_session(price_id, empresa_id):
    """Crea una sesión única de pago en Stripe y devuelve la URL mágica"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            # Cambia estas URLs por tu dominio real cuando pases a producción
            success_url='http://localhost:8501/?pago=exito', 
            cancel_url='http://localhost:8501/?pago=cancelado',
            # ESTO ES CRÍTICO: Le dice a tu Webhook qué empresa acaba de pagar
            client_reference_id=empresa_id 
        )
        return session.url
    except Exception as e:
        st.error(f"Error conectando con el banco: {e}")
        return None

def mostrar_ui_suscripcion(plan_actual, empresa_id):
    """Muestra el panel de control de ventas en la sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏢 Mi Suscripción")

    # IDs de tus productos en Stripe
    PRICE_PRO = "price_1T6tvXEnVY2TFI6OKL0Iu5gd"
    PRICE_BUSINESS = "price_1T6twbEnVY2TFI6O2DUCRJen"

    if plan_actual == 'starter' or not plan_actual:
        st.sidebar.warning("Plan actual: **Starter** (Límite 100 reg.)")
        st.sidebar.markdown("¿El negocio crece? Elimina los límites.")

        if st.sidebar.button("🚀 Upgrade a Pro (19€/mes)"):
            url = crear_checkout_session(PRICE_PRO, empresa_id)
            if url:
                st.sidebar.markdown(f"[💳 Haz clic aquí para pagar de forma segura]({url})")

        if st.sidebar.button("💼 Upgrade a Business (49€/mes)"):
            url = crear_checkout_session(PRICE_BUSINESS, empresa_id)
            if url:
                st.sidebar.markdown(f"[💳 Haz clic aquí para pagar de forma segura]({url})")

    elif plan_actual == 'pro':
        st.sidebar.success("Plan actual: **Pro** (Ilimitado)")
        st.sidebar.markdown("Estás en el plan profesional.")
        # Opcional: Botón para saltar a Business si tienes funciones extra

    elif plan_actual == 'business':
        st.sidebar.success("Plan actual: **Business** (VIP)")
        st.sidebar.markdown("Cuentas con todas las funciones activas.")
# Manejo de la key de Stripe asegurando que no rompa si no está configurada aún
try:
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY') or st.secrets.get('STRIPE_SECRET_KEY')
except Exception:
    pass 

st.set_page_config(
    page_title='AB Software Empresarial',
    page_icon='S',
    layout='wide',
    initial_sidebar_state='expanded'
)

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

from services.db_context import DBContext

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

from views.dashboard_view import render_dashboard
from views.gastos_view import render_gastos_view
from views.inventory_view import render_inventory_view
from views.flota_view import render_flota_view
from views.rrhh_view import render_rrhh_view
from views.presupuestos_view import render_presupuestos_view
from views.eco_view import render_eco_view

def main():
    # --- 1. HANDLER DE PAGOS STRIPE ---
    if st.query_params.get('pago') == 'exito':
        st.balloons()
        st.success("🎉 ¡Pago confirmado! Tu cuenta ha sido actualizada al Plan Pro con éxito.")
        st.query_params.clear() # Limpiamos la URL
        
        # Si el usuario ya estaba logueado en esta pestaña, le actualizamos el plan en directo
        if st.session_state.get('loggedin') and 'empresa_id' in st.session_state:
            try:
                emp_data = db_admin.table('empresas').select('plan').eq('id', st.session_state.empresa_id).execute()
                if emp_data.data:
                    st.session_state.plan = emp_data.data[0]['plan']
            except:
                pass

    elif st.query_params.get('pago') == 'cancelado':
        st.warning("❌ Pago cancelado o incompleto.")
        st.query_params.clear()

    # --- 2. VERIFICACIÓN PÚBLICA ---
    if 'num' in st.query_params and 'hash' in st.query_params:
        from views.verify_public import render_verify_public
        render_verify_public(db)
        return

    # --- 3. GESTIÓN DE SESIÓN ---
    if 'loggedin' not in st.session_state:
        st.session_state.loggedin = False

    if not st.session_state.loggedin:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            try:
                st.image('assets/logo_ext.png', use_container_width=True)
            except Exception:
                st.markdown('<h1 style=text-align:center>AB Software</h1>', unsafe_allow_html=True)

            st.markdown('### Acceso al Sistema')
            with st.form('login_master'):
                u = st.text_input('Usuario', placeholder='admin')
                p = st.text_input('Contrasena', type='password')
                submitted = st.form_submit_button('ENTRAR', use_container_width=True)

            if submitted:
                try:
                    auth = AuthService(db_admin)
                    res = auth.login(u, p)
                    if res['success']:
                        empresa_id = res['user']['empresa_id']
                        st.session_state.loggedin = True
                        st.session_state.username = u
                        st.session_state.empresaid = empresa_id
                        st.session_state.empresa_id = empresa_id
                        st.session_state.rol = res['user'].get('rol', 'user')
                        
                        # 🔥 RECUPERAMOS PLAN Y ESTADO DE PAGO
                        try:
                            emp_data = db_admin.table('empresas').select('plan, estado_pago').eq('id', empresa_id).execute()
                            if emp_data.data:
                                st.session_state.plan = emp_data.data[0].get('plan') or 'starter'
                                st.session_state.estado_pago = emp_data.data[0].get('estado_pago') or 'activo'
                            else:
                                st.session_state.plan = 'starter'
                                st.session_state.estado_pago = 'activo'
                        except Exception:
                            st.session_state.plan = 'starter'
                            st.session_state.estado_pago = 'activo'
                            
                        st.rerun()
                    else:
                        st.error('Credenciales invalidas')
                except Exception as e:
                    st.error(f'Error de autenticacion: {e}')
        return

    # --- 4. VERIFICACIÓN DE IMPAGOS (Muro de Pago) ---
    if st.session_state.get('estado_pago') == 'impago':
        st.error("### 🛑 Cuenta Suspendida")
        st.warning("No hemos podido procesar el cobro de tu suscripción Pro.")
        st.info("Para recuperar el acceso a tus datos y funciones, por favor actualiza tu método de pago.")
        st.link_button("💳 Gestionar Pago en Stripe", "https://billing.stripe.com/p/login/test_dRm28r8M1emrd9PbZucEw00")
        if st.button("Cerrar Sesión"):
            st.session_state.loggedin = False
            st.rerun()
        st.stop() # 🛑 Detiene todo. No se renderiza nada más.

    # --- 5. SIDEBAR Y MENÚ ---
    with st.sidebar:
        try:
            st.image('assets/logo_ext.png', use_container_width=True)
        except Exception:
            st.markdown('### AB Software')

        st.markdown(f'**Usuario:** {st.session_state.username}')
        st.markdown('---')

        # Panel de Stripe
        mostrar_ui_suscripcion(st.session_state.get('plan', 'starter'), st.session_state.empresa_id)

        # Navegación según el rol
        if st.session_state.get('rol') == 'admin':
            opciones = ['Dashboard', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad', 'Admin']
        else:
            opciones = ['Dashboard', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad']

        menu = st.radio('NAVEGACION', opciones, label_visibility='collapsed')
        st.markdown('---')

        if st.button('CERRAR SESION', use_container_width=True):
            st.session_state.loggedin = False
            st.rerun()

    # --- 6. RENDERIZADO DE VISTAS (Dejas lo que ya tenías abajo) ---
    try:
        if menu == 'Dashboard':
            render_dashboard(db)
        elif menu == 'Gastos':
            render_gastos_view(db)
        elif menu == 'Presupuestos':
            render_presupuestos_view(db)
        elif menu == 'Inventario':
            render_inventory_view(db)
        elif menu == 'Flota':
            render_flota_view(db)
        elif menu == 'RRHH':
            render_rrhh_view(db)
        elif menu == 'Sostenibilidad':
            render_eco_view(db)
        elif menu == 'Admin':
            from views.superadmin_view import render_superadmin_view
            render_superadmin_view(db)
    except Exception as e:
        st.error(f'Error cargando el modulo {menu}: {e}')
        st.exception(e)

if __name__ == '__main__':
    main()