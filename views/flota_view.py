import streamlit as st
import pandas as pd
from datetime import date


def render_flota_view(db):
    st.title("🚛 Gestión Integral de Activos y Flota")
    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid:
        st.error("Error crítico: no se ha detectado el ID de empresa en la sesión.")
        return

    # Carga de datos resiliente
    try:
        res = db.table("flota").select("*").eq("empresa_id", eid).execute()
        df = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Error cargando flota: {e}")
        return

    # Estructura de pestañas profesional
    tab_crud, tab_taller, tab_finance = st.tabs(
        ["📝 Inventario de Vehículos", "🔧 Libro de Taller", "📉 Análisis Financiero"])

    # --- 1. GESTIÓN (ALTA/BAJA/MODIFICACIÓN) ---
    with tab_crud:
        st.subheader("Base de Datos de Vehículos")
        st.caption("Modifica celdas directamente. Usa la papelera para dar de baja. Añade filas al final.")

        if df.empty:
            df = pd.DataFrame(
                columns=["id", "vehiculo", "matricula", "precio_compra", "km_actual", "estado", "tipo_motor"])

        # Configuración del Editor
        column_config = {
            "precio_compra": st.column_config.NumberColumn("Coste Adq. (€)", format="%.2f €", min_value=0),
            "km_actual": st.column_config.NumberColumn("Kilometraje", format="%d km"),
            "tipo_motor": st.column_config.SelectboxColumn("Motorización",
                                                           options=["Diesel", "Gasolina", "Híbrido", "Eléctrico"],
                                                           required=True),
            "estado": st.column_config.SelectboxColumn("Estado", options=["Operativo", "En Taller", "Baja", "Vendido"],
                                                       required=True),
            "id": st.column_config.TextColumn("ID Sistema", disabled=True)
        }

        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config=column_config,
            key="editor_flota_master",
            hide_index=True
        )

        # Botón de Sincronización (Critical Path)
        if st.button("💾 GUARDAR CAMBIOS EN BASE DE DATOS", type="primary"):
            try:
                # 1. Identificar registros
                data_to_save = edited_df.to_dict('records')

                # 2. Limpieza y preparación
                for row in data_to_save:
                    row['empresa_id'] = eid
                    # Si es nuevo (no tiene ID o es nan), Supabase lo crea
                    if pd.isna(row.get('id')):
                        if 'id' in row: del row['id']

                # 3. Estrategia de sustitución segura (Upsert)
                # Nota: Para máxima pureza, lo ideal es detectar diffs, pero "Delete All + Insert"
                # por empresa_id es atómico y seguro en escalas pequeñas/medianas.
                # Si tienes muchos mantenimientos vinculados, habría que usar UPSERT row by row.
                # Aquí asumimos UPSERT por ID si existe.

                for row in data_to_save:
                    db.table("flota").upsert(row).execute()

                # Manejo de borrados (Lo que ya no está en edited_df pero sí en DB)
                if not df.empty:
                    ids_originales = set(df['id'].dropna().tolist())
                    ids_nuevos = set(edited_df['id'].dropna().tolist())
                    ids_borrar = ids_originales - ids_nuevos
                    for id_b in ids_borrar:
                        db.table("flota").delete().eq("id", id_b).execute()

                st.success("✅ Base de datos actualizada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error crítico al guardar: {e}")

    # --- 2. TALLER ---
    with tab_taller:
        st.subheader("🛠️ Gestión de Mantenimiento")

        if not df.empty:
            # Selector inteligente (Matrícula + Coche)
            opciones_vehiculo = df.apply(lambda x: f"{x['matricula']} - {x['vehiculo']}", axis=1)
            seleccion = st.selectbox("Seleccione Vehículo a intervenir:", opciones_vehiculo, key="sel_taller_pro")

            matricula_sel = seleccion.split(" - ")[0]

            with st.form("taller_entry"):
                c1, c2 = st.columns(2)
                f_entrada = c1.date_input("Fecha Entrada", value=date.today())
                tipo_int = c2.selectbox("Tipo Intervención",
                                        ["Mecánica General", "Carrocería", "Neumáticos", "Electrónica", "ITV"])

                c3, c4 = st.columns(2)
                coste = c3.number_input("Coste Factura (€)", min_value=0.0, step=10.0)
                kms = c4.number_input("Kilómetros al entrar", min_value=0)

                desc = st.text_area("Detalle de trabajos realizados")

                if st.form_submit_button("Registrar Historial"):
                    db.table("mantenimiento_flota").insert({
                        "empresa_id": eid,
                        "vehiculo": matricula_sel,
                        "fecha": str(f_entrada),
                        "tipo": tipo_int,
                        "coste": coste,
                        "kilometros": kms,
                        "descripcion": desc
                    }).execute()
                    st.success(f"Entrada registrada para {matricula_sel}")
        else:
            st.warning("No hay vehículos dados de alta para realizar mantenimientos.")

    # --- 3. ANÁLISIS FINANCIERO (AMORTIZACIÓN) ---
    with tab_finance:
        st.subheader("📉 Plan de Amortización de Activos")

        if not df.empty:
            sel_fin = st.selectbox("Analizar Activo:", df["matricula"].unique(), key="sel_finance")
            # Extraer datos del vehículo seleccionado
            dato_v = df[df["matricula"] == sel_fin].iloc[0]

            valor_compra = float(dato_v.get("precio_compra", 0) or 0)

            if valor_compra > 0:
                col_inputs, col_summary = st.columns([1, 2])

                with col_inputs:
                    st.markdown("#### Parámetros")
                    anos_vida = st.number_input("Vida Útil (Años)", min_value=1, value=5, step=1)
                    valor_residual = st.number_input("Valor Residual (€)", min_value=0.0, value=0.0)

                # Cálculo Lineal
                base_amortizable = valor_compra - valor_residual
                cuota_anual = base_amortizable / anos_vida

                with col_summary:
                    st.markdown("#### Resumen Contable")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Valor Inicial", f"{valor_compra:,.2f} €")
                    m2.metric("Amortización Anual", f"{cuota_anual:,.2f} €", delta="-Gasto")
                    m3.metric("Valor Residual", f"{valor_residual:,.2f} €")

                # Tabla Detallada
                st.markdown("#### Cuadro de Amortización")
                lista_amort = []
                acumulado = 0
                vnc = valor_compra

                for i in range(1, anos_vida + 1):
                    acumulado += cuota_anual
                    vnc -= cuota_anual
                    lista_amort.append({
                        "Año": f"Año {i}",
                        "Cuota Anual": cuota_anual,
                        "Amort. Acumulada": acumulado,
                        "Valor Neto Contable": vnc
                    })

                df_amort = pd.DataFrame(lista_amort)
                st.dataframe(
                    df_amort.style.format({
                        "Cuota Anual": "{:,.2f} €",
                        "Amort. Acumulada": "{:,.2f} €",
                        "Valor Neto Contable": "{:,.2f} €"
                    }),
                    use_container_width=True
                )
            else:
                st.info("Este activo no tiene valor de compra asignado. Edítalo en la pestaña 'Inventario'.")