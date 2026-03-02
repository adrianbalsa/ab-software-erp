import streamlit as st
import hashlib
import datetime


def render_registro_view(db_admin):
    st.title("🚀 Crear cuenta en AB Software")
    st.caption("Configura tu empresa y accede al ERP en menos de 2 minutos.")
    st.divider()

    with st.form("form_registro_empresa"):
        st.markdown("### 🏢 Datos de la empresa")
        col1, col2 = st.columns(2)
        nif = col1.text_input("NIF/CIF *", placeholder="B12345678", max_chars=12)
        nombre_legal = col2.text_input("Razón social *", placeholder="Mi Empresa S.L.")
        col3, col4 = st.columns(2)
        nombre_comercial = col3.text_input("Nombre comercial", placeholder="Mi Empresa")
        plan = col4.selectbox("Plan", ["starter", "professional", "business", "enterprise"])
        col5, col6 = st.columns(2)
        email_empresa = col5.text_input("Email empresa *", placeholder="admin@miempresa.com")
        telefono = col6.text_input("Teléfono", placeholder="600000000")
        direccion = st.text_input("Dirección fiscal", placeholder="Calle Mayor 1, 15001 A Coruña")

        st.markdown("### 👤 Usuario administrador")
        col7, col8 = st.columns(2)
        username = col7.text_input("Nombre de usuario *", placeholder="admin")
        email_user = col8.text_input("Email usuario *", placeholder="tu@email.com")
        col9, col10 = st.columns(2)
        password = col9.text_input("Contraseña *", type="password", min_value=8 if False else 0)
        password2 = col10.text_input("Repetir contraseña *", type="password")

        st.markdown("### 📋 Condiciones")
        acepta_rgpd = st.checkbox("Acepto la política de privacidad y el tratamiento de datos (RGPD)")
        acepta_terminos = st.checkbox("Acepto los términos y condiciones del servicio")

        submitted = st.form_submit_button("✅ Crear mi cuenta", type="primary", use_container_width=True)

        if submitted:
            # Validaciones
            errores = []
            if not nif or len(nif.strip()) < 8:
                errores.append("NIF/CIF inválido (mínimo 8 caracteres)")
            if not nombre_legal:
                errores.append("La razón social es obligatoria")
            if not email_empresa or "@" not in email_empresa:
                errores.append("Email de empresa inválido")
            if not username or len(username.strip()) < 3:
                errores.append("El usuario debe tener al menos 3 caracteres")
            if not email_user or "@" not in email_user:
                errores.append("Email de usuario inválido")
            if not password or len(password) < 8:
                errores.append("La contraseña debe tener al menos 8 caracteres")
            if password != password2:
                errores.append("Las contraseñas no coinciden")
            if not acepta_rgpd:
                errores.append("Debes aceptar la política de privacidad")
            if not acepta_terminos:
                errores.append("Debes aceptar los términos y condiciones")

            if errores:
                for err in errores:
                    st.error(f"❌ {err}")
            else:
                try:
                    # Verificar que el NIF no existe ya
                    res_check = db_admin.table("empresas").select("id").eq(
                        "nif", nif.strip().upper()
                    ).execute()
                    if res_check.data:
                        st.error("❌ Ya existe una empresa registrada con ese NIF.")
                        st.stop()

                    # Verificar que el username no existe
                    res_usr_check = db_admin.table("usuarios").select("id").eq(
                        "username", username.strip().lower()
                    ).execute()
                    if res_usr_check.data:
                        st.error("❌ Ese nombre de usuario ya está en uso.")
                        st.stop()

                    # 1. Crear empresa
                    res_emp = db_admin.table("empresas").insert({
                        "nif": nif.strip().upper(),
                        "nombre_legal": nombre_legal.strip(),
                        "nombre_comercial": nombre_comercial.strip() or nombre_legal.strip(),
                        "plan_suscripcion": plan,
                        "email": email_empresa.strip().lower(),
                        "telefono": telefono.strip() or None,
                        "direccion": direccion.strip() or None,
                        "activa": True,
                        "fecha_registro": str(datetime.date.today()),
                    }).execute()

                    if not res_emp.data:
                        st.error("❌ Error creando la empresa. Inténtalo de nuevo.")
                        st.stop()

                    empresa_id = res_emp.data[0]["id"]

                    # 2. Crear usuario administrador
                    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
                    db_admin.table("usuarios").insert({
                        "username": username.strip().lower(),
                        "email": email_user.strip().lower(),
                        "password_hash": password_hash,
                        "rol": "admin",
                        "activo": True,
                        "empresa_id": empresa_id,
                        "fecha_creacion": str(datetime.datetime.now()),
                    }).execute()

                    # 3. Mostrar éxito
                    st.balloons()
                    st.success(f"✅ Cuenta creada correctamente para **{nombre_legal}**")
                    st.info(f"🔑 Accede con el usuario: **{username.strip().lower()}**")
                    st.divider()
                    st.markdown("**Próximos pasos:**")
                    st.markdown("1. Ve a la pantalla de inicio de sesión")
                    st.markdown("2. Introduce tu usuario y contraseña")
                    st.markdown("3. Configura tu empresa en el panel de administración")

                except Exception as e:
                    st.error(f"❌ Error durante el registro: {e}")

    st.divider()
    st.caption("¿Ya tienes cuenta? Vuelve a la pantalla de inicio de sesión.")
