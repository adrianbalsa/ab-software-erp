from services.verifactu_service import VerifactuService
import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import json
import time


# FUNCIÓN AUXILIAR: Verificar si puede editarse
# ============================================
def puede_editar_presupuesto(row):
    """
    Verifica si un presupuesto/factura puede editarse.
    Regla: Solo se pueden editar borradores y presupuestos no facturados.
    Las facturas emitidas están bloqueadas permanentemente.
    """
    # Si está marcado como bloqueado, no se puede editar
    if row.get('bloqueado'):
        return False

    # Si ya está facturado, no se puede editar
    if row.get('estado') == 'Facturado':
        return False

    # Si es anulación o rectificativa, no se puede editar
    if row.get('tipo_factura') in ['ANULACION', 'RECTIFICATIVA']:
        return False

    # En cualquier otro caso (Borrador, Enviado, Aceptado), sí se puede
    return True
class PresupuestoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'PRESUPUESTO / QUOTE', 0, 1, 'R')
        self.ln(5)
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Documento Oficial de Valoración Económica', 0, 1, 'R')
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} - AB Software Enterprise ERP', 0, 0, 'C')


def generar_pdf_completo(datos):
    import tempfile
    import os

    pdf = PresupuestoPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    es_factura = datos.get('num_factura') and 'FAC-' in datos.get('num_factura', '')

    pdf.set_font('Arial', 'B', 14)
    if es_factura:
        pdf.cell(0, 8, 'FACTURA OFICIAL', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f"Número: {datos.get('num_factura', 'N/A')}", 0, 1, 'L')
    else:
        pdf.cell(0, 8, 'PRESUPUESTO / QUOTATION', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, f"Ref: {datos.get('proyecto', 'N/A')}", 0, 1, 'L')

    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    y_qr = pdf.get_y()

    pdf.set_font('Arial', 'B', 9)
    pdf.cell(100, 5, 'EMITIDO POR:', 0, 0)
    pdf.set_xy(110, pdf.get_y())
    pdf.cell(0, 5, 'CLIENTE:', 0, 1)

    pdf.set_font('Arial', '', 8.5)
    pdf.cell(100, 4, datos.get('nombre_empresa', 'AB Software Solutions S.L.'), 0, 0)
    pdf.set_xy(110, pdf.get_y())
    pdf.cell(0, 4, datos['cliente'], 0, 1)
    pdf.cell(100, 4, f"CIF: {datos.get('nif_empresa', '')}", 0, 0)
    pdf.set_xy(110, pdf.get_y())
    if es_factura and datos.get('nif_cliente'):
        pdf.cell(0, 4, f"NIF: {datos.get('nif_cliente', 'N/A')}", 0, 1)
    else:
        pdf.cell(0, 4, f"Proyecto: {datos.get('proyecto', 'N/A')}", 0, 1)

    pdf.cell(100, 4, f"Fecha: {datos['fecha']}", 0, 1)

    if es_factura and datos.get('hash_factura'):
        try:
            from services.qr_helper import QRHelper
            qr_img = QRHelper.generar_qr_factura(
                num_factura=datos['num_factura'],
                hash_factura=datos['hash_factura'],
                dominio="https://absoftware.es"
            )

            if qr_img:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(qr_img.read())
                    qr_path = tmp.name

                pdf.image(qr_path, x=165, y=y_qr, w=25, h=25)
                pdf.set_xy(160, y_qr + 27)
                pdf.set_font('Arial', 'I', 7)
                pdf.cell(40, 3, 'Código QR Verifactu', 0, 1, 'C')
                os.unlink(qr_path)
        except Exception as e:
            print(f"Error QR: {e}")

    pdf.ln(3)

    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(100, 7, 'CONCEPTO / DESCRIPCION', 1, 0, 'L', True)
    pdf.cell(20, 7, 'CANT.', 1, 0, 'C', True)
    pdf.cell(25, 7, 'P.UNIT.', 1, 0, 'R', True)
    pdf.cell(30, 7, 'TOTAL', 1, 1, 'R', True)

    pdf.set_font('Arial', '', 8.5)
    for item in datos.get('items', []):
        desc = item.get('Descripción', 'Concepto')
        try:
            desc = desc.encode('latin-1', 'replace').decode('latin-1')
        except:
            desc = "Descripcion (caracteres invalidos)"

        cant = float(item.get('Cantidad', 1))
        precio = float(item.get('Precio', 0))
        total_linea = float(item.get('Total', 0))

        desc_short = desc[0:65] if len(desc) > 65 else desc
        pdf.cell(100, 6, desc_short, 1)
        pdf.cell(20, 6, f"{cant:.1f}", 1, 0, 'C')
        pdf.cell(25, 6, f"{precio:.2f}", 1, 0, 'R')
        pdf.cell(30, 6, f"{total_linea:.2f}", 1, 1, 'R')

    pdf.ln(3)

    pdf.set_x(145)
    pdf.set_font('Arial', '', 9)
    pdf.cell(30, 5, 'Subtotal:', 0, 0, 'R')
    subtotal = datos.get('subtotal_neto', datos['total'])
    pdf.cell(25, 5, f"{subtotal:.2f}", 0, 1, 'R')

    pdf.set_x(145)
    pdf.cell(30, 5, 'IVA / Impuestos:', 0, 0, 'R')
    impuestos = datos.get('impuestos', 0)
    pdf.cell(25, 5, f"{impuestos:.2f}", 0, 1, 'R')

    pdf.set_x(145)
    pdf.set_draw_color(0, 0, 0)
    pdf.line(145, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)

    pdf.set_x(145)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(30, 7, 'TOTAL:', 0, 0, 'R')
    pdf.cell(25, 7, f"{datos['total']:.2f} {datos.get('moneda', 'EUR')}", 0, 1, 'R')

    pdf.ln(5)

    pdf.set_font('Arial', '', 8)
    pdf.set_text_color(80, 80, 80)
    if es_factura:
        pdf.multi_cell(0, 3.5,
            "DOCUMENTO OFICIAL DE FACTURA expedida conforme a la normativa fiscal vigente. "
            "Documento identificado y sellado mediante sistema Verifactu (Real Decreto-ley 4/2023). "
            "Conservar para auditoría fiscal."
        )
    else:
        pdf.multi_cell(0, 3.5,
            "VALIDEZ: Esta propuesta es válida por 30 días calendario. "
            "Condición: Se requiere aceptación escrita y depósito del 50% para iniciar trabajos. "
            "IVA incluido en los precios especificados."
        )

    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output(dest='S'))

def render_presupuestos_view(db):
    st.title("💰 Área Comercial y Financiera")

    eid = st.session_state.get("empresaid") or st.session_state.get("empresa_id")
    if not eid:
        st.error("Error Critico: No se ha detectado el ID de empresa en la sesion.")
        return

    # NUEVO: cargar datos empresa una sola vez por sesión
    if 'datos_empresa' not in st.session_state:
        try:
            res_emp = db.table('empresas').select(
                'nif, nombre_legal, nombre_comercial, direccion, municipio, provincia'
            ).eq('id', eid).single().execute()
            st.session_state['datos_empresa'] = res_emp.data if res_emp.data else {}
        except Exception:
            st.session_state['datos_empresa'] = {}


    tab_creacion, tab_gestion = st.tabs(["✨ Editor de Presupuestos (Calculadora)", "🗂️ Gestión de Facturación"])

    with tab_creacion:
        st.subheader("Nueva Propuesta Económica")

        with st.container(border=True):
            col_cab1, col_cab2 = st.columns(2)
            col_cab3, col_cab4 = st.columns(2)

            cliente = col_cab1.text_input("Cliente / Razón Social", placeholder="Ej: Tech Solutions SL")
            nif_cliente = col_cab2.text_input(
                "NIF/CIF Cliente",
                placeholder="B12345678",
                help="⚠️ OBLIGATORIO para facturación con Verifactu"
            )
            proyecto = col_cab3.text_input("Referencia Proyecto / Obra",
                                          placeholder="Ej: Reforma Oficinas Centrales")
            moneda = col_cab4.selectbox("Divisa del Proyecto", ["EUR", "CHF", "USD", "GBP"])

        st.markdown("---")

        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown("#### 🏗️ Ingeniería y Servicios")

            st.caption("Partida 1: Obra Civil / Metros")
            cc1, cc2 = st.columns(2)
            metros_obra = cc1.number_input("Cantidad (m²)", min_value=0.0, step=1.0, format="%.2f")
            precio_m2 = cc2.number_input(f"Precio Unitario ({moneda}/m²)", min_value=0.0, value=0.0, step=10.0)
            subtotal_obra = metros_obra * precio_m2

            st.markdown("---")
            st.caption("Partida 2: Recursos Humanos")
            mo1, mo2, mo3 = st.columns(3)
            num_trabajadores = mo1.number_input("Nº Trabajadores", min_value=0, value=0, step=1)
            horas_por_trab = mo2.number_input("Horas/Trabajador", min_value=0.0, value=0.0, step=0.5)
            coste_hora = mo3.number_input(f"Coste/Hora ({moneda})", min_value=0.0, value=0.0, step=5.0)
            total_horas_humanas = num_trabajadores * horas_por_trab
            subtotal_mo = total_horas_humanas * coste_hora

            if subtotal_obra > 0 or subtotal_mo > 0:
                st.info(f"Subtotal Servicios: {(subtotal_obra + subtotal_mo):,.2f} {moneda}")

        with col_der:
            st.markdown("#### 📦 Suministros y Materiales")

            if "df_materiales_presu" not in st.session_state:
                st.session_state.df_materiales_presu = pd.DataFrame(
                    [{"Descripción": "", "Cantidad": 1.0, "Precio": 0.0}]
                )

            st.caption("Añade líneas de materiales, hardware o licencias:")
            edited_df = st.data_editor(
                st.session_state.df_materiales_presu,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Precio": st.column_config.NumberColumn(format="%.2f")
                },
                key="editor_materiales_presupuesto"
            )

            try:
                df_calc = edited_df[edited_df["Descripción"] != ""]
                subtotal_materiales = (df_calc["Cantidad"] * df_calc["Precio"]).sum()
            except:
                subtotal_materiales = 0.0

            st.success(f"Subtotal Materiales: {subtotal_materiales:,.2f} {moneda}")

        st.markdown("---")

        c_res1, c_res2 = st.columns([1, 1.5])

        with c_res1:
            st.subheader("💰 Totalización")

            margen = st.number_input("Margen Comercial (%)", min_value=0.0, value=15.0, step=1.0)
            iva_pct = st.number_input("I.V.A. Aplicable (%)", min_value=0.0, value=21.0, step=1.0)

            subtotal_obra_final = subtotal_obra * (1 + margen / 100)
            subtotal_mo_final = subtotal_mo * (1 + margen / 100)
            subtotal_materiales_final = subtotal_materiales * (1 + margen / 100)

            subtotal_final = subtotal_obra_final + subtotal_mo_final + subtotal_materiales_final
            cuota_iva = subtotal_final * (iva_pct / 100)
            total_final = subtotal_final + cuota_iva

            st.info(f"Subtotal Servicios: {subtotal_final:,.2f} {moneda}")
            st.metric(label="PRESUPUESTO FINAL (IVA INC.)", value=f"{total_final:,.2f} {moneda}")

            if st.button("💾 REGISTRAR PRESUPUESTO", type="primary", use_container_width=True):
                if not cliente or not proyecto:
                    st.error("❌ Faltan datos obligatorios: Cliente y Proyecto.")
                else:
                    items_detalle = []

                    if subtotal_obra > 0:
                        items_detalle.append({
                            "Descripción": f"Ejecución de Obra Civil ({metros_obra} m2)",
                            "Cantidad": metros_obra,
                            "Precio": precio_m2 * (1 + margen / 100),
                            "Total": subtotal_obra * (1 + margen / 100)
                        })

                    if subtotal_mo > 0:
                        items_detalle.append({
                            "Descripción": f"Mano de Obra Especializada ({num_trabajadores} operarios x {horas_por_trab}h)",
                            "Cantidad": total_horas_humanas,
                            "Precio": coste_hora * (1 + margen / 100),
                            "Total": subtotal_mo * (1 + margen / 100)
                        })

                    for index, row in edited_df.iterrows():
                        if row["Descripción"] and row["Precio"] > 0:
                            p_unit = row["Precio"] * (1 + margen / 100)
                            tot = (row["Cantidad"] * row["Precio"]) * (1 + margen / 100)
                            items_detalle.append({
                                "Descripción": row["Descripción"],
                                "Cantidad": row["Cantidad"],
                                "Precio": p_unit,
                                "Total": tot
                            })

                    try:
                        datos_insert = {
                            "empresa_id": eid,
                            "cliente": cliente,
                            "nif_cliente": nif_cliente,
                            "titulo": proyecto,
                            "total_neto": subtotal_final,
                            "impuestos": cuota_iva,
                            "total_final": total_final,
                            "iva_porcentaje": iva_pct,
                            "moneda": moneda,
                            "estado": "Pendiente",
                            "fecha": str(datetime.date.today()),
                            "items": json.dumps(items_detalle),
                            "observaciones": f"Margen aplicado: {margen}%"
                        }

                        db.table("presupuestos").insert(datos_insert).execute()
                        st.balloons()
                        st.success("✅ Presupuesto registrado correctamente en el sistema.")
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error de Base de Datos: {e}")

        with c_res2:
            st.subheader("📧 Generador de Email Corporativo")
            lang_email = st.selectbox("Idioma del Correo", ["Español", "English", "Deutsch", "Français"])

            texto_email = ""
            if lang_email == "Español":
                texto_email = f"""Estimado/a responsable de {cliente},

Adjunto le remitimos la propuesta económica detallada correspondiente al proyecto "{proyecto}".

Hemos realizado un ajuste técnico para optimizar los costes manteniendo los estándares de calidad.

RESUMEN ECONÓMICO:
Total Presupuesto: {total_final:,.2f} {moneda}

Quedamos a su entera disposición para cualquier aclaración o revisión de partidas.

Atentamente,
El Equipo Comercial."""

            elif lang_email == "English":
                texto_email = f"""Dear {cliente},

Please find attached the detailed quotation for the project "{proyecto}".

We have optimized the technical requirements to ensure the best value for money.

FINANCIAL SUMMARY:
Total Quote: {total_final:,.2f} {moneda}

We remain at your disposal for any further questions.

Sincerely,
Sales Team."""

            elif lang_email == "Deutsch":
                texto_email = f"""Sehr geehrte Damen und Herren von {cliente},

anbei erhalten Sie das detaillierte Angebot für das Projekt "{proyecto}".

GESAMTSUMME:
{total_final:,.2f} {moneda}

Für Rückfragen stehen wir Ihnen gerne zur Verfügung.

Mit freundlichen Grüßen,
Ihr Verkaufsteam."""

            else:
                texto_email = f"""Cher client {cliente},

Veuillez trouver ci-joint le devis détaillé pour le projet "{proyecto}".

RÉSUMÉ FINANCIER:
Montant Total: {total_final:,.2f} {moneda}

Nous restons à votre entière disposition.

Cordialement,
L'équipe commerciale."""

            st.text_area("Copiar y Pegar en Cliente de Correo:", value=texto_email, height=300)

    with tab_gestion:
        st.subheader("🗂️ Control de Presupuestos y Facturación")

        try:
            res = db.table("presupuestos").select(
                "id, fecha, cliente, titulo, total_final, total_neto, impuestos, "
                "moneda, estado, num_factura, numero_secuencial, hash_factura, "
                "nif_cliente, nif_empresa, items, observaciones, bloqueado, tipo_factura"
            ).eq("empresa_id", eid).order("fecha", desc=True).execute()

            df_hist = pd.DataFrame(res.data)
        except Exception as e:
            st.error(f"Error cargando historial: {e}")
            df_hist = pd.DataFrame()

        if df_hist.empty:
            st.info("No hay presupuestos registrados todavía.")
        else:
            c_pen, c_fac, c_tot = st.columns(3)

            pendientes = df_hist[df_hist["estado"] == "Pendiente"]
            facturados = df_hist[df_hist["estado"] == "Facturado"]

            c_pen.metric("Pendientes de Aprobar", len(pendientes), border=True)
            c_fac.metric("Facturados / Ganados", len(facturados), border=True)
            c_tot.metric("Volumen Total Ofertado", f"{df_hist['total_final'].sum():,.2f}", border=True)

            st.divider()
            # Añadir columna visual de tipo de factura
            if not df_hist.empty:
                if 'tipo_factura' in df_hist.columns:
                    df_hist['📋'] = df_hist['tipo_factura'].fillna('NORMAL').map({
                        'NORMAL': '✅',
                        'RECTIFICATIVA': '📝',
                        'ANULACION': '🚫'
                    })
                else:
                    df_hist['📋'] = '✅'

                # Función para colorear filas según tipo
                def colorear_tipo_factura(row):
                    tipo = row.get('tipo_factura', 'NORMAL')
                    if tipo == 'ANULACION':
                        return ['background-color: rgba(255, 100, 100, 0.2)'] * len(row)
                    elif tipo == 'RECTIFICATIVA':
                        return ['background-color: rgba(255, 200, 100, 0.2)'] * len(row)
                    else:
                        return [''] * len(row)
            df_display = df_hist[["fecha", "cliente", "titulo", "total_final", "moneda", "estado", "num_factura"]]
            st.dataframe(
                df_display.style.apply(colorear_tipo_factura, axis=1),
                use_container_width=True,
                hide_index=True
            )

            st.divider()

            col_accion_fac, col_accion_pdf = st.columns(2)

            with col_accion_fac:
                st.markdown("### ⚡ Emitir Factura")
                st.caption("Convierte un presupuesto aceptado en factura oficial.")
                
                pendientes = df_hist[
                    (df_hist["estado"].isin(["Pendiente", "Aceptado"])) &
                    (df_hist["bloqueado"].fillna(False) == False)
                ]
                if not pendientes.empty:
                    opcion_fac = st.selectbox(
                        "Selecciona Presupuesto a Facturar:",
                        options=pendientes["id"].tolist(),
                        format_func=lambda x: f"{df_hist[df_hist['id'] == x]['cliente'].values[0]} - {df_hist[df_hist['id'] == x]['total_final'].values[0]:.2f} (ID:{x})"
                    )

                    if st.button("✅ GENERAR FACTURA OFICIAL"):
                        from services.verifactu_service import VerifactuService
                        verifactu = VerifactuService(db)

                        presupuesto = df_hist[df_hist['id'] == opcion_fac].iloc[0]

                        if not presupuesto.get('nif_cliente'):
                            st.error("❌ El presupuesto debe tener el NIF del cliente para facturar.")
                            st.stop()

                        num_secuencial = verifactu.obtener_numero_secuencial(eid)
                        if not num_secuencial:
                            st.error("❌ Error generando número secuencial.")
                            st.stop()

                        año = datetime.date.today().year
                        num_factura = f"FAC-{año}-{num_secuencial:06d}"
                        hash_anterior = verifactu.obtener_hash_anterior(eid)

                        if 'datos_empresa' not in st.session_state:
                            res_emp = db.table('empresas').select('nif, nombre_legal').eq('id', eid).single().execute()
                            st.session_state['datos_empresa'] = res_emp.data if res_emp.data else {}

                        datos_hash = {
                            'nif_empresa': st.session_state['datos_empresa'].get('nif', ''),
                            'nif_cliente': presupuesto.get('nif_cliente', ''),
                            'num_factura': num_factura,
                            'fecha': str(datetime.date.today()),
                            'total': float(presupuesto['total_final'])
                        }

                        hash_factura = verifactu.generar_hash_factura(datos_hash, hash_anterior)

                        try:
                            db.table("presupuestos").update({
                                "estado": "Facturado",
                                "num_factura": num_factura,
                                "numero_secuencial": num_secuencial,
                                "fecha_factura": str(datetime.date.today()),
                                "hash_factura": hash_factura,
                                "hash_anterior": hash_anterior,
                                "nif_empresa": datos_hash['nif_empresa'],
                                "bloqueado": True,  # ← NUEVO: Bloquear factura emitida
                                "tipo_factura": "NORMAL"  # ← NUEVO: Marcar como factura normal
                            }).eq("id", opcion_fac).execute()
                            verifactu.registrar_auditoria("GENERAR_FACTURA_VERIFACTU", "presupuestos", opcion_fac,
                                                        {"num_factura": num_factura,
                                                         "hash": hash_factura[:16] + "...",
                                                         "num_secuencial": num_secuencial})

                            st.success(f"✅ Factura {num_factura} generada con Verifactu")
                            st.info(f"🔒 Hash: {hash_factura[:16]}...")
                            st.balloons()
                            time.sleep(1.5)
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al generar factura: {e}")
                else:
                    st.info("No tienes presupuestos pendientes para facturar.")

            # ========== SECCIÓN: ANULACIÓN Y RECTIFICACIÓN DE FACTURAS ==========
            st.markdown("### ⚠️ Gestión de Facturas Emitidas")
            st.caption(
                "Las facturas emitidas no se pueden borrar. Solo se anulan o rectifican para mantener trazabilidad fiscal.")

            col_anular, col_rectificar = st.columns(2)

            # ---------- COLUMNA IZQUIERDA: ANULACIÓN ----------
            with col_anular:
                st.markdown("#### 🚫 Anular Factura")
                st.caption("Para facturas emitidas por error. La factura queda registrada como anulada (no se borra).")

                # Filtrar solo facturas emitidas no anuladas
                facturas_anulables = df_hist[
                    (df_hist['estado'] == 'Facturado') &
                    (df_hist['tipo_factura'].fillna('NORMAL') != 'ANULACION')
                ] if not df_hist.empty and 'tipo_factura' in df_hist.columns else (
                    df_hist[df_hist['estado'] == 'Facturado'] if not df_hist.empty else pd.DataFrame()
                )

                if not facturas_anulables.empty:
                    opcion_anular = st.selectbox(
                        "Selecciona factura a anular:",
                        options=facturas_anulables["id"].tolist(),
                        format_func=lambda x: (
                            f"{df_hist[df_hist['id'] == x]['num_factura'].values[0]} | "
                            f"{df_hist[df_hist['id'] == x]['cliente'].values[0]} | "
                            f"{df_hist[df_hist['id'] == x]['total_final'].values[0]:.2f}€"
                        ),
                        key="sel_anular"
                    )

                    motivo_anulacion = st.text_area(
                        "Motivo de anulación (obligatorio):",
                        placeholder="Ej: Factura duplicada, emitida por error, cancelación de servicio...",
                        key="motivo_anular",
                        height=80
                    )

                    if st.button("🚫 ANULAR FACTURA", type="secondary", use_container_width=True):
                        if not motivo_anulacion or len(motivo_anulacion.strip()) < 10:
                            st.error("❌ Debes indicar un motivo de anulación (mínimo 10 caracteres)")
                        else:
                            from services.verifactu_service import VerifactuService
                            verifactu = VerifactuService(db)

                            resultado = verifactu.anular_factura(
                                factura_id=opcion_anular,
                                usuario=st.session_state.username,
                                motivo=motivo_anulacion
                            )

                            if resultado['success']:
                                st.success("✅ Factura anulada correctamente")
                                st.info("La factura queda registrada como anulada en el sistema para auditoría fiscal.")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error(f"❌ {resultado['error']}")
                else:
                    st.info("ℹ️ No hay facturas emitidas disponibles para anular")

            # ---------- COLUMNA DERECHA: RECTIFICACIÓN ----------
            with col_rectificar:
                st.markdown("#### 📝 Rectificar Factura")
                st.caption("Crea una nueva factura que corrige una anterior. La original permanece intacta.")

                # Filtrar facturas emitidas normales (no anuladas ni ya rectificativas)
                facturas_rectificables = df_hist[
                    (df_hist['estado'] == 'Facturado') &
                    (df_hist['tipo_factura'].fillna('NORMAL') == 'NORMAL')
                ] if not df_hist.empty and 'tipo_factura' in df_hist.columns else (
                    df_hist[df_hist['estado'] == 'Facturado'] if not df_hist.empty else pd.DataFrame()
                )

                if not facturas_rectificables.empty:
                    opcion_rect = st.selectbox(
                        "Selecciona factura a rectificar:",
                        options=facturas_rectificables["id"].tolist(),
                        format_func=lambda x: (
                            f"{df_hist[df_hist['id'] == x]['num_factura'].values[0]} | "
                            f"{df_hist[df_hist['id'] == x]['cliente'].values[0]}"
                        ),
                        key="sel_rect"
                    )

                    # Mostrar datos actuales de la factura
                    factura_rect = df_hist[df_hist['id'] == opcion_rect].iloc[0]
                    st.info(
                        f"📊 Total actual: **{factura_rect['total_final']:.2f} {factura_rect.get('moneda', 'EUR')}**")

                    nuevo_total = st.number_input(
                        "Nuevo importe total:",
                        min_value=0.0,
                        value=float(factura_rect['total_final']),
                        step=0.01,
                        key="nuevo_total_rect",
                        help="El nuevo importe que debe reflejar la factura rectificativa"
                    )

                    motivo_rect = st.text_area(
                        "Motivo de rectificación (obligatorio):",
                        placeholder="Ej: Error en cálculo IVA, descuento no aplicado, cambio en unidades...",
                        key="motivo_rect",
                        height=80
                    )

                    if st.button("📝 CREAR FACTURA RECTIFICATIVA", type="primary", use_container_width=True):
                        if not motivo_rect or len(motivo_rect.strip()) < 10:
                            st.error("❌ Debes indicar el motivo de rectificación (mínimo 10 caracteres)")
                        else:
                            from services.verifactu_service import VerifactuService
                            verifactu = VerifactuService(db)

                            cambios = {
                                'total': nuevo_total,
                                'motivo': motivo_rect,
                                'nif_cliente': factura_rect.get('nif_cliente'),
                                'cliente': factura_rect['cliente'],
                                'total_neto': nuevo_total / 1.21,  # Simplificación (asume IVA 21%)
                                'impuestos': nuevo_total - (nuevo_total / 1.21)
                            }

                            resultado = verifactu.crear_factura_rectificativa(
                                factura_origen_id=opcion_rect,
                                empresa_id=eid,
                                cambios=cambios
                            )

                            if resultado['success']:
                                st.success(
                                    f"✅ Factura rectificativa **{resultado['num_factura']}** creada correctamente")
                                st.info(f"🔒 Hash Verifactu: `{resultado['hash'][:24]}...`")
                                diferencia = nuevo_total - factura_rect['total_final']
                                if diferencia > 0:
                                    st.warning(f"⬆️ Incremento: +{diferencia:.2f}€")
                                elif diferencia < 0:
                                    st.warning(f"⬇️ Reducción: {diferencia:.2f}€")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {resultado['error']}")
                else:
                    st.info("ℹ️ No hay facturas normales disponibles para rectificar")

            st.divider()
            with col_accion_pdf:
                st.markdown("### 📄 Descargar Documento")
                st.caption("Genera el PDF del presupuesto o factura.")

                opcion_pdf = st.selectbox(
                    "Selecciona Documento:",
                    options=df_hist["id"].tolist(),
                    format_func=lambda x: (
                        f"{'FACTURA ' + df_hist[df_hist['id'] == x]['num_factura'].values[0] if df_hist[df_hist['id'] == x]['num_factura'].values[0] and df_hist[df_hist['id'] == x]['num_factura'].values[0] != '' else 'Presupuesto'} | "
                        f"{df_hist[df_hist['id'] == x]['titulo'].values[0] if 'titulo' in df_hist.columns else 'Sin título'} | "
                        f"{df_hist[df_hist['id'] == x]['cliente'].values[0]}"
                    )
                )

                if opcion_pdf:
                    row = df_hist[df_hist["id"] == opcion_pdf].iloc[0]

                    try:
                        items_dec = json.loads(row["items"]) if isinstance(row["items"], str) else row["items"]
                    except:
                        items_dec = []

                    # Leer datos empresa desde BD (una sola vez por sesión)
                    if 'datos_empresa' not in st.session_state:
                        res_emp = db.table('empresas').select(
                            'nif, nombre_legal, nombre_comercial, direccion, municipio, provincia'
                        ).eq('id', eid).single().execute()
                        st.session_state['datos_empresa'] = res_emp.data if res_emp.data else {}

                    empresa = st.session_state['datos_empresa']

                    datos_reporte = {
                        'cliente': row['cliente'],
                        'proyecto': row.get('titulo', 'Sin título'),
                        'fecha': str(row.get('fecha_factura') or row.get('fecha') or datetime.date.today()),
                        'total': row['total_final'],
                        'moneda': row['moneda'],
                        'items': items_dec,
                        'num_factura': row.get('num_factura'),
                        'hash_factura': row.get('hash_factura'),
                        'nif_empresa': empresa.get('nif', ''),  # ← desde BD
                        'nombre_empresa': empresa.get('nombre_legal', empresa.get('nombre_comercial', '')),
                        'nif_cliente': row.get('nif_cliente'),
                        'subtotal_neto': row.get('total_neto'),
                        'impuestos': row.get('impuestos')
                    }
                    pdf_bytes = generar_pdf_completo(datos_reporte)

                    nombre_fichero = f"Presupuesto_{row['cliente']}_{row['fecha']}.pdf"
                    if row["estado"] == "Facturado" and row.get("num_factura"):
                        nombre_fichero = f"FACTURA_{row['num_factura'].replace('/', '_')}.pdf"

                    st.download_button(
                        label="⬇️ DESCARGAR PDF",
                        data=pdf_bytes,
                        file_name=nombre_fichero,
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )

            st.divider()

            st.markdown("### 📊 Auditoría Verifactu")

            if st.button("📥 Exportar Libro de Registros (AEAT)", use_container_width=True):
                from services.verifactu_service import VerifactuService
                verifactu = VerifactuService(db)

                año_actual = datetime.date.today().year
                res_libro = db.table("presupuestos").select(
                    "numero_secuencial, num_factura, fecha_factura, cliente, "
                    "nif_cliente, total_final, moneda, hash_factura"
                ).eq("empresa_id", eid).eq("estado", "Facturado").order("numero_secuencial", desc=False).execute()

                if res_libro.data:
                    df_libro = pd.DataFrame(res_libro.data)
                    df_libro["Año"] = año_actual
                    df_libro = df_libro[[
                        "Año", "numero_secuencial", "num_factura", "fecha_factura",
                        "nif_cliente", "cliente", "total_final", "moneda", "hash_factura"
                    ]]

                    df_libro.columns = [
                        "Ejercicio Fiscal", "Nº Secuencial", "Número Factura", "Fecha Emisión",
                        "NIF/CIF Cliente", "Razón Social", "Base Imponible", "Moneda", "Hash SHA-256"
                    ]

                    csv_libro = df_libro.to_csv(index=False, encoding='utf-8-sig', sep=';')

                    st.download_button(
                        "⬇️ Descargar Libro_Verifactu_2026.csv",
                        csv_libro,
                        f"Libro_Verifactu_{año_actual}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                    st.success(f"✅ {len(df_libro)} facturas en el registro")
                else:
                    st.warning("⚠️ No hay facturas Verifactu para exportar")

            if st.button("🔍 Auditar Integridad de Cadena", use_container_width=True):
                from services.verifactu_service import VerifactuService
                verifactu = VerifactuService(db)

                res_audit = db.table("presupuestos").select(
                    "id, num_factura, hash_factura, hash_anterior, numero_secuencial"
                ).eq("empresa_id", eid).eq("estado", "Facturado").order("numero_secuencial", desc=False).execute()

                if not res_audit.data:
                    st.info("Sin facturas para auditar")
                else:
                    errores = []
                    for i, factura in enumerate(res_audit.data):
                        if i > 0:
                            hash_previo_esperado = res_audit.data[i - 1]["hash_factura"]
                            hash_previo_real = factura["hash_anterior"]

                            if hash_previo_esperado != hash_previo_real:
                                errores.append({
                                    "factura": factura["num_factura"],
                                    "problema": "Cadena de hash rota"
                                })

                    if len(errores) == 0:
                        st.success("✅ **CADENA ÍNTEGRA** - Sin manipulación detectada")
                        st.info(f"🔗 {len(res_audit.data)} facturas verificadas correctamente")
                    else:
                        st.error(f"❌ **ALERTA**: {len(errores)} facturas con problemas")
                        st.json(errores)