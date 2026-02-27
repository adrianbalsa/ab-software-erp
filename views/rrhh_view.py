import streamlit as st
import pandas as pd
from datetime import date


def render_rrhh_view(db):
    st.title("Recursos Humanos y Control Horario")
    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid:
        st.error("Error critico: no se ha detectado el ID de empresa en la sesion.")
        return

    tab_horas, tab_historial = st.tabs(["Registro de Jornada", "Historial de Equipo"])

    with tab_horas:
        st.subheader("Nuevo Parte de Horas")
        with st.form("form_horas_pro"):
            col1, col2 = st.columns(2)
            empleado = col1.text_input("Nombre Empleado / Operario")
            fecha = col2.date_input("Fecha Jornada", value=date.today())
            col3, col4 = st.columns(2)
            try:
                res_proy = db.table("presupuestos").select("proyecto").eq("empresa_id", eid).execute()
                lista_proy = [p["proyecto"] for p in res_proy.data if p.get("proyecto")]
                lista_proy.append("Interno / Taller")
            except Exception:
                lista_proy = ["General"]
            proyecto = col3.selectbox("Proyecto Asignado", lista_proy)
            horas = col4.number_input("Horas Imputadas", min_value=0.5, max_value=24.0, step=0.5, value=8.0)
            desc = st.text_area("Descripcion de Tareas")
            if st.form_submit_button("FICHAR HORAS"):
                if empleado:
                    try:
                        db.table("horas").insert({
                            "empresa_id": eid,
                            "empleado": empleado,
                            "fecha": str(fecha),
                            "proyecto": proyecto,
                            "horas": horas,
                            "descripcion": desc
                        }).execute()
                        st.success("Jornada registrada correctamente.")
                    except Exception as e:
                        st.error(f"Error guardando: {e}")
                else:
                    st.warning("Indica el nombre del empleado.")

    with tab_historial:
        st.subheader("Informe de Actividad")
        try:
            res = db.table("horas").select("*").eq("empresa_id", eid).order("fecha", desc=True).execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                st.info(f"Total Horas Registradas: {df['horas'].sum()}h")
                st.dataframe(df[["fecha", "empleado", "proyecto", "horas", "descripcion"]], use_container_width=True)
            else:
                st.info("No hay registros de horas.")
        except Exception as e:
            st.error(f"No se pudo cargar el historial: {e}")