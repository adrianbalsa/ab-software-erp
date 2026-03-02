import streamlit as st
from supabase import create_client
from services.auth_service import AuthService
import time

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

try:
    if 'SUPABASE_URL' in st.secrets and 'SUPABASE_KEY' in st.secrets:
        db = create_client(st.secrets['SUPABASE_URL'], st.secrets['SUPABASE_KEY'])
        from services.db_context import DBContext
        db = DBContext(db)
        db_admin = create_client(
            st.secrets['SUPABASE_URL'],
            st.secrets.get('SUPABASE_SERVICE_KEY', st.secrets['SUPABASE_KEY'])
        )
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
    if 'num' in st.query_params and 'hash' in st.query_params:
        from views.verify_public import render_verify_public
        render_verify_public(db)
        return

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
                        st.rerun()
                    else:
                        st.error('Credenciales invalidas')
                except Exception as e:
                    st.error(f'Error de autenticacion: {e}')
        return

    with st.sidebar:
        try:
            st.image('assets/logo_ext.png', use_container_width=True)
        except Exception:
            st.markdown('### AB Software')

        st.markdown(f'**Usuario:** {st.session_state.username}')
        st.markdown('---')

        if st.session_state.get('rol') == 'admin':
            opciones = ['Dashboard', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad', 'Admin']
        else:
            opciones = ['Dashboard', 'Gastos', 'Presupuestos', 'Inventario', 'Flota', 'RRHH', 'Sostenibilidad']

        menu = st.radio('NAVEGACION', opciones, label_visibility='collapsed')
        st.markdown('---')

        if st.button('CERRAR SESION', use_container_width=True):
            st.session_state.loggedin = False
            st.rerun()

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
