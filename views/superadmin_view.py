import streamlit as st
import pandas as pd
import datetime
from services.pdf_service import generar_pdf_factura

def render_superadmin_view(db):
    if st.session_state.get("rol") != "admin":
        st.error("Acceso denegado. Solo el administrador puede acceder a este panel.")
        return

    st.title("⚙️ Panel de Administración")
    st.caption("Gestión global de empresas, usuarios y métricas del SaaS")

    tab_empresas, tab_usuarios, tab_metricas, tab_auditoria, tab_facturacion = st.tabs(
        ["🏢 Empresas", "👤 Usuarios", "📊 Métricas SaaS", "🔍 Auditoría", "📄 Facturación"]
    )

    # ─────────────────────────────────────────
    # TAB 1: EMPRESAS
    # ─────────────────────────────────────────
    with tab_empresas:
        st.subheader("Empresas registradas")

        try:
            res = db.table("empresas").select(
                "id, nif, nombrelegal, nombre_comercial, plan, activa, fecha_registro"
            ).order("fecha_registro", desc=True).execute()
            empresas = res.data or []
        except Exception as e:
            st.error(f"Error cargando empresas: {e}")
            empresas = []

        if empresas:
            df_emp = pd.DataFrame(empresas)
            cols_mostrar = [c for c in ["nombre_comercial", "nif", "plan", "activa", "fecha_registro"] if c in df_emp.columns]
            st.dataframe(df_emp[cols_mostrar], use_container_width=True, hide_index=True)
        else:
            st.info("No hay empresas registradas.")

        st.divider()

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
                                "nombrelegal": nombre_legal.strip(),
                                "nombre_comercial": nombre_comercial.strip() or nombre_legal.strip(),
                                "plan": plan,
                                "email": email.strip() or None,
                                "telefono": telefono.strip() or None,
                                "direccion": direccion.strip() or None,
                                "activa": True,
                            }).execute()
                            st.success(f"Empresa {nombre_legal} creada correctamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error creando empresa: {e}")

        if empresas:
            st.divider()
            st.markdown("**Cambiar plan o estado**")
            nombres = [f"{e['nombre_comercial']} ({e['nif']})" for e in empresas]
            col_sel, col_plan, col_estado = st.columns(3)
            idx = col_sel.selectbox("Empresa", options=list(range(len(empresas))), format_func=lambda i: nombres[i])
            empresa_sel = empresas[idx]
            nuevo_plan = col_plan.selectbox(
                "Nuevo plan",
                ["starter", "professional", "business", "enterprise"],
                index=["starter", "professional", "business", "enterprise"].index(empresa_sel.get("plan", "starter")) if empresa_sel.get("plan") in ["starter", "professional", "business", "enterprise"] else 0
            )
            nueva_activa = col_estado.checkbox("Empresa activa", value=bool(empresa_sel.get("activa", True)))
            if st.button("Guardar cambios", type="primary", use_container_width=True):
                try:
                    db.table("empresas").update({
                        "plan": nuevo_plan,
                        "activa": nueva_activa,
                    }).eq("id", empresa_sel["id"]).execute()
                    st.success("Actualizado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ─────────────────────────────────────────
    # TAB 2: USUARIOS
    # ─────────────────────────────────────────
    with tab_usuarios:
        st.subheader("Usuarios del sistema")

        try:
            res_usr = db.table("usuarios").select(
                "id, username, email, rol, activo, empresa_id, fecha_creacion"
            ).order("fecha_creacion", desc=True).execute()
            usuarios = res_usr.data or []
        except Exception as e:
            st.error(f"Error cargando usuarios: {e}")
            usuarios = []

        if usuarios:
            df_usr = pd.DataFrame(usuarios)

            try:
                res_emp = db.table("empresas").select("id, nombre_comercial").execute()
                mapa_empresas = {e["id"]: e["nombre_comercial"] for e in (res_emp.data or [])}
                df_usr["empresa"] = df_usr["empresa_id"].map(mapa_empresas).fillna("Sin empresa")
            except Exception:
                df_usr["empresa"] = df_usr.get("empresa_id", "")

            filtro_empresa = st.selectbox(
                "Filtrar por empresa:",
                options=["Todas"] + list(mapa_empresas.values()) if 'mapa_empresas' in dir() else ["Todas"],
                key="filtro_empresa_usuarios"
            )

            if filtro_empresa != "Todas":
                empresa_id_filtro = [k for k, v in mapa_empresas.items() if v == filtro_empresa]
                if empresa_id_filtro:
                    df_usr = df_usr[df_usr["empresa_id"] == empresa_id_filtro[0]]

            cols_usr = [c for c in ["username", "email", "rol", "activo", "empresa", "fecha_creacion"] if c in df_usr.columns]
            st.dataframe(df_usr[cols_usr], use_container_width=True, hide_index=True)
            st.caption(f"{len(df_usr)} usuarios encontrados")
        else:
            st.info("No hay usuarios registrados.")

        st.divider()

        if usuarios:
            st.markdown("**Modificar usuario**")
            nombres_usr = [f"{u.get('username', 'N/A')} ({u.get('email', '')})" for u in usuarios]
            idx_usr = st.selectbox("Usuario", options=list(range(len(usuarios))), format_func=lambda i: nombres_usr[i], key="sel_usr_mod")
            usr_sel = usuarios[idx_usr]

            col_rol, col_activo = st.columns(2)
            nuevo_rol = col_rol.selectbox(
                "Rol",
                ["user", "manager", "admin"],
                index=["user", "manager", "admin"].index(usr_sel.get("rol", "user")) if usr_sel.get("rol") in ["user", "manager", "admin"] else 0
            )
            nuevo_activo = col_activo.checkbox("Usuario activo", value=bool(usr_sel.get("activo", True)))

            if st.button("Guardar cambios de usuario", type="primary", use_container_width=True):
                try:
                    db.table("usuarios").update({
                        "rol": nuevo_rol,
                        "activo": nuevo_activo,
                    }).eq("id", usr_sel["id"]).execute()
                    st.success("Usuario actualizado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ─────────────────────────────────────────
    # TAB 3: MÉTRICAS SAAS
    # ─────────────────────────────────────────
    with tab_metricas:
        st.subheader("📈 Rendimiento Financiero SaaS")

        try:
            res_fac = db.table("facturas").select("total_factura, fecha_emision, cuota_iva").execute()
            df_fac = pd.DataFrame(res_fac.data or [])

            if not df_fac.empty:
                df_fac['fecha_emision'] = pd.to_datetime(df_fac['fecha_emision'])
                
                total_bruto = df_fac['total_factura'].sum()
                total_iva = df_fac['cuota_iva'].sum()
                ingreso_neto = total_bruto - total_iva
                n_clientes = df_fac['total_factura'].count()
                arpu = ingreso_neto / n_clientes if n_clientes > 0 else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Ingresos Brutos", f"{total_bruto:,.2f} €")
                c2.metric("IVA a Liquidar", f"{total_iva:,.2f} €")
                c3.metric("Ingreso Neto (EBITDA)", f"{ingreso_neto:,.2f} €", delta="SaaS Revenue")
                c4.metric("Clientes Pago", n_clientes)

                st.write("### Evolución de Ingresos (Netos)")
                df_chart = df_fac.set_index('fecha_emision').resample('D')['total_factura'].sum().reset_index()
                st.area_chart(data=df_chart, x='fecha_emision', y='total_factura')
                
                st.success(f"Ticket medio por cliente: {arpu:.2f} €")
            else:
                st.info("Esperando la primera venta para generar estadísticas...")
                
        except Exception as e:
            st.error(f"Error calculando métricas financieras: {e}")

    # ─────────────────────────────────────────
    # TAB 4: AUDITORÍA
    # ─────────────────────────────────────────
    with tab_auditoria:
        st.subheader("Registro de auditoría")

        col_f1, col_f2, col_f3 = st.columns(3)
        filtro_accion = col_f1.text_input("Filtrar por acción", placeholder="GENERAR_FACTURA...")
        filtro_tabla = col_f2.text_input("Filtrar por tabla", placeholder="presupuestos")
        filtro_limite = col_f3.number_input("Últimos N registros", min_value=10, max_value=500, value=100, step=10)

        try:
            query = db.table("auditoria").select(
                "id, accion, tabla, registro_id, empresa_id, timestamp"
            ).order("timestamp", desc=True).limit(int(filtro_limite))

            res_aud = query.execute()
            auditoria = res_aud.data or []
        except Exception as e:
            st.error(f"Error cargando auditoría: {e}")
            auditoria = []

        if auditoria:
            df_aud = pd.DataFrame(auditoria)

            if filtro_accion:
                df_aud = df_aud[df_aud["accion"].str.contains(filtro_accion.upper(), na=False)]
            if filtro_tabla:
                df_aud = df_aud[df_aud["tabla"].str.contains(filtro_tabla.lower(), na=False)]

            st.dataframe(df_aud, use_container_width=True, hide_index=True)
            st.caption(f"{len(df_aud)} registros mostrados")

            csv_aud = df_aud.to_csv(index=False, encoding="utf-8-sig", sep=";")
            st.download_button(
                "⬇️ Exportar auditoría CSV",
                csv_aud,
                f"auditoria_{datetime.date.today()}.csv",
                "text/csv",
                use_container_width=True
            )
        else:
            st.info("No hay registros de auditoría.")

    # ─────────────────────────────────────────
    # TAB 5: FACTURACIÓN
    # ─────────────────────────────────────────
    with tab_facturacion:
        st.subheader("Emisión y Descarga de Facturas")
        st.markdown("Aquí se listarán las facturas generadas por Stripe.")
        
        factura_test = {
            'numero_factura': 'FAC-2026-001',
            'total_factura': 19.00
        }
        
        if st.button(f"⬇️ Descargar PDF de prueba ({factura_test['numero_factura']})", type="primary"):
            datos_emisor = {"nombre": "AB SOFTWARE ERP", "nif": "B12345678", "hash": "VERIFACTU-TEST-99"}
            datos_receptor = {"nombre": st.session_state.username, "id": st.session_state.empresa_id}
            conceptos = [{"nombre": "Suscripción Plan Pro", "precio": factura_test['total_factura']}]
            
            try:
                pdf_bytes = generar_pdf_factura(datos_emisor, datos_receptor, conceptos)
                st.download_button(
                    label="✅ Confirmar Descarga PDF",
                    data=pdf_bytes,
                    file_name=f"{factura_test['numero_factura']}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Falta el archivo pdf_service.py o hay un error: {e}")