import streamlit as st
import pandas as pd
import datetime


def render_superadmin_view(db):
    # Control de acceso
    if st.session_state.get("rol") != "admin":
        st.error("Acceso denegado. Solo el administrador puede acceder a este panel.")
        return

    st.title("⚙️ Panel de Administración")
    st.caption("Gestión global de empresas, usuarios y métricas del SaaS")

    tab_empresas, tab_usuarios, tab_metricas, tab_auditoria = st.tabs(
        ["🏢 Empresas", "👤 Usuarios", "📊 Métricas SaaS", "🔍 Auditoría"]
    )

    # ─────────────────────────────────────────
    # TAB 1: GESTIÓN DE EMPRESAS
    # ─────────────────────────────────────────
    with tab_empresas:
        st.subheader("Empresas registradas")

        try:
            res = db.table("empresas").select(
                "id, nif, nombre_legal, nombre_comercial, plan_suscripcion, activa, fecha_registro"
            ).order("fecha_registro", desc=True).execute()
            empresas = res.data or []
        except Exception as e:
            st.error(f"Error cargando empresas: {e}")
            empresas = []

        if empresas:
            df_emp = pd.DataFrame(empresas)
            cols_mostrar = [
                c for c in ["nombre_comercial", "nif", "plan_suscripcion", "activa", "fecha_registro"]
                if c in df_emp.columns
            ]
            st.dataframe(df_emp[cols_mostrar], use_container_width=True, hide_index=True)
        else:
            st.info("No hay empresas registradas.")

        st.divider()

        # Crear nueva empresa
        with st.expander("➕ Crear nueva empresa"):
            with st.form("form_nueva_empresa"):
                col1, col2 = st.columns(2)
                nif = col1.text_input("NIF/CIF *", placeholder="B12345678", max_chars=12)
                nombre_legal = col2.text_input("Razón social *", placeholder="Empresa S.L.")
                col3, col4 = st.columns(2)
                nombre_comercial = col3.text_input("Nombre comercial", placeholder="Empresa")
                plan = col4.selectbox("Plan", ["starter", "professional", "business", "enterprise"])
                col5, col6 = st.columns(2)
                email = col5.text_input("Email", placeholder="admin@empresa.com")
                telefono = col6.text_input("Teléfono", placeholder="600000000")
                direccion = st.text_input("Dirección", placeholder="Calle Mayor 1, 15001 A Coruña")

                submitted = st.form_submit_button("Crear empresa", type="primary", use_container_width=True)
                if submitted:
                    if not nif or not nombre_legal:
                        st.error("NIF y razón social son obligatorios.")
                    elif len(nif) > 12:
                        st.error("El NIF no puede superar 12 caracteres.")
                    else:
                        try:
                            db.table("empresas").insert({
                                "nif": nif.strip().upper(),
                                "nombre_legal": nombre_legal.strip(),
                                "nombre_comercial": nombre_comercial.strip() or nombre_legal.strip(),
                                "plan_suscripcion": plan,
                                "email": email.strip() or None,
                                "telefono": telefono.strip() or None,
                                "direccion": direccion.strip() or None,
                                "activa": True,
                            }).execute()
                            st.success(f"Empresa {nombre_legal} creada correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creando empresa: {e}")

        # Cambiar plan de suscripción
        if empresas:
            st.divider()
            st.markdown("**Cambiar plan de suscripción**")

            nombres = [f"{e['nombre_comercial']} ({e['nif']})" for e in empresas]
            col_sel, col_plan, col_estado = st.columns(3)

            idx = col_sel.selectbox("Empresa", options=list(range(len(empresas))),
                                    format_func=lambda i: nombres[i])
            empresa_sel = empresas[idx]

            nuevo_plan = col_plan.selectbox(
                "Nuevo plan",
                ["starter", "professional", "business", "enterprise"],
                index=["starter", "professional", "business", "enterprise"].index(
                    empresa_sel.get("plan_suscripcion", "starter")
                )
            )

            activa_actual = bool(empresa_sel.get("activa", True))
            nueva_activa = col_estado.checkbox("Empresa activa", value=activa_actual)

            if st.button("Guardar cambios de plan", type="primary", use_container_width=True):
                try:
                    db.table("empresas").update({
                        "plan_suscripcion": nuevo_plan,
                        "activa": nueva_activa,
                    }).eq("id", empresa_sel["id"]).execute()
                    st.success("Plan y estado actualizados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error actualizando empresa: {e}")

    # El resto de tabs (Usuarios, Métricas, Auditoría) puedes dejarlos en blanco
    # o implementarlos más adelante sin afectar al resto del sistema.