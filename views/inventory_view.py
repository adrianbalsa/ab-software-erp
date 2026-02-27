import streamlit as st
import pandas as pd


def render_inventory_view(db):
    st.title("📦 Control de Stock y Almacén")
    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid:
        st.error("Error crítico: no se ha detectado el ID de empresa en la sesión.")
        return

    # Carga de datos
    try:
        res = db.table("inventario").select("*").eq("empresa_id", eid).execute()
        df = pd.DataFrame(res.data)
    except:
        df = pd.DataFrame()

    col_gestion, col_vista = st.columns([1, 2])

    # --- COLUMNA IZQUIERDA: OPERATIVA ---
    with col_gestion:
        st.subheader("⚙️ Operativa")

        tab_mov, tab_alta = st.tabs(["🔄 Movimientos", "🆕 Alta Producto"])

        # PESTAÑA MOVIMIENTOS (ENTRADA/SALIDA)
        with tab_mov:
            if not df.empty:
                st.caption("Registrar entradas o salidas de material.")

                item_sel = st.selectbox("Referencia", df["nombre"].unique(), key="sel_mov_item")
                tipo_mov = st.radio("Tipo de Movimiento", ["🔻 Salida (Consumo)", "🔺 Entrada (Reposición)"],
                                    horizontal=True)
                cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)

                # Datos actuales para feedback
                stock_actual = df[df["nombre"] == item_sel]["stock"].values[0]
                st.info(f"Stock Actual: {stock_actual} unidades")

                if st.button("Confirmar Movimiento", use_container_width=True):
                    nuevo_stock = stock_actual
                    if "Salida" in tipo_mov:
                        if cantidad > stock_actual:
                            st.error("❌ No hay suficiente stock para esta salida.")
                            st.stop()
                        nuevo_stock -= cantidad
                    else:
                        nuevo_stock += cantidad

                    # Update DB
                    try:
                        db.table("inventario").update({"stock": nuevo_stock}).eq("nombre", item_sel).execute()
                        st.success(f"✅ Operación realizada. Nuevo stock: {nuevo_stock}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error DB: {e}")
            else:
                st.warning("Inventario vacío. Da de alta productos primero.")

        # PESTAÑA ALTA NUEVA REFERENCIA
        with tab_alta:
            with st.form("form_alta_stock"):
                nombre = st.text_input("Nombre Artículo/Ref.")
                categoria = st.selectbox("Categoría",
                                         ["Herramientas", "Consumibles", "Repuestos", "EPIs", "Material Oficina",
                                          "Otros"])
                stock_ini = st.number_input("Stock Inicial", min_value=0)
                minimo = st.number_input("Stock Seguridad (Min)", min_value=1, help="Nivel donde saltará la alerta")

                if st.form_submit_button("Crear Referencia"):
                    if nombre:
                        try:
                            db.table("inventario").insert({
                                "empresa_id": eid,
                                "nombre": nombre,
                                "categoria": categoria,
                                "stock": stock_ini,
                                "minimo": minimo
                            }).execute()
                            st.success("Referencia creada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                    else:
                        st.error("El nombre es obligatorio.")

    # --- COLUMNA DERECHA: VISUALIZACIÓN ---
    with col_vista:
        st.subheader("📊 Estado de Existencias")

        if not df.empty:
            # Filtros
            cats_disp = df["categoria"].unique() if "categoria" in df.columns else ["General"]
            filtro_cat = st.multiselect("Filtrar por Categoría", options=cats_disp, default=cats_disp)

            # Aplicar filtro
            if "categoria" in df.columns:
                df_view = df[df["categoria"].isin(filtro_cat)]
            else:
                df_view = df

            # Lógica de colores (Highlight)
            def color_stock(val):
                # Esta función recibe la fila entera si usamos axis=1
                color = '#5e1b1b' if val['stock'] <= val['minimo'] else ''  # Rojo oscuro para fondo
                return [f'background-color: {color}' for _ in val]

            st.markdown(f"Mostrando **{len(df_view)}** referencias.")

            # Tabla estilizada
            st.dataframe(
                df_view[["nombre", "categoria", "stock", "minimo"]].style.apply(color_stock, axis=1),
                use_container_width=True,
                height=500
            )

            # Resumen de Alertas
            bajos = df_view[df_view['stock'] <= df_view['minimo']]
            if not bajos.empty:
                st.error(f"⚠️ ATENCIÓN: Tienes {len(bajos)} productos por debajo del mínimo de seguridad.")
        else:
            st.info("No hay datos en el inventario.")