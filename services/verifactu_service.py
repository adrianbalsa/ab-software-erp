import hashlib
import json
import datetime
import streamlit as st


class VerifactuService:

    def __init__(self, db_client):
        self.db = db_client

    def obtener_numero_secuencial(self, empresa_id):
        try:
            result = self.db.table("presupuestos").select("numero_secuencial").eq("empresa_id", empresa_id).not_.is_("numero_secuencial", "null").order("numero_secuencial", desc=True).limit(1).execute()
            if result.data:
                return int(result.data[0]["numero_secuencial"]) + 1
            return 1
        except Exception as e:
            st.error(f"Error secuencial: {e}")
            return None

    def obtener_hash_anterior(self, empresa_id):
        try:
            result = self.db.table("presupuestos").select("hash_factura").eq("empresa_id", empresa_id).eq("estado", "Facturado").not_.is_("hash_factura", "null").order("numero_secuencial", desc=True).limit(1).execute()
            if result.data:
                return result.data[0]["hash_factura"]
            return None
        except Exception as e:
            st.error(f"Error hash anterior: {e}")
            return None

    def generar_hash_factura(self, datos_factura, hash_anterior=None):
        try:
            cadena = (
                str(datos_factura["nif_empresa"])
                + str(datos_factura["nif_cliente"])
                + str(datos_factura["num_factura"])
                + str(datos_factura["fecha"])
                + "{:.2f}".format(float(datos_factura["total"]))
            )
            if hash_anterior:
                cadena += hash_anterior
            return hashlib.sha256(cadena.encode("utf-8")).hexdigest()
        except Exception as e:
            st.error(f"Error hash: {e}")
            return None

    def emitir_factura_desde_presupuesto(self, presupuesto_row, prefijo_serie, nif_emisor):
        empresa_id = presupuesto_row.get("empresa_id")
        if not empresa_id:
            return {"success": False, "error": "Falta empresa_id"}
        numero_secuencial = self.obtener_numero_secuencial(empresa_id)
        if not numero_secuencial:
            return {"success": False, "error": "Error numero secuencial"}
        hash_anterior = self.obtener_hash_anterior(empresa_id)
        anio = datetime.date.today().year
        num_factura = "{}-{}-{:06d}".format(prefijo_serie, anio, numero_secuencial)
        fecha = presupuesto_row.get("fecha_factura") or presupuesto_row.get("fecha")
        base = float(presupuesto_row.get("total_neto") or 0)
        impuestos = float(presupuesto_row.get("impuestos") or 0)
        total = float(presupuesto_row.get("total_final") or presupuesto_row.get("total") or (base + impuestos))
        datos_hash = {
            "nif_empresa": nif_emisor,
            "nif_cliente": presupuesto_row.get("nif_cliente") or "",
            "num_factura": num_factura,
            "fecha": str(fecha),
            "total": total,
        }
        hash_factura = self.generar_hash_factura(datos_hash, hash_anterior)
        if not hash_factura:
            return {"success": False, "error": "Error generando hash"}
        return {
            "success": True,
            "num_factura": num_factura,
            "hash_factura": hash_factura,
            "hash_anterior": hash_anterior,
            "fecha_factura": fecha,
            "total_neto": base,
            "impuestos": impuestos,
            "total_final": total,
            "numero_secuencial": numero_secuencial,
            "bloqueado": True,
            "estado": "Facturado",
            "tipo_factura": "NORMAL",
        }

    def verificar_hash(self, hash_factura, datos_factura, hash_anterior=None):
        return self.generar_hash_factura(datos_factura, hash_anterior) == hash_factura

    def registrar_auditoria(self, accion, tabla, registro_id, cambios):
        try:
            self.db.table("auditoria").insert({
                "accion": accion,
                "tabla": tabla,
                "registro_id": str(registro_id),
                "cambios": json.dumps(cambios),
                "fecha": str(datetime.datetime.now()),
                "empresa_id": st.session_state.get("empresa_id", "unknown"),
            }).execute()
        except Exception as e:
            st.warning(f"Auditoria no registrada: {e}")

    def anular_factura(self, factura_id, usuario, motivo):
        try:
            res = self.db.table("presupuestos").select("num_factura,empresa_id,numero_secuencial").eq("id", factura_id).execute()
            if not res.data:
                return {"success": False, "error": "Factura no encontrada"}
            factura = res.data[0]
            self.db.table("presupuestos").update({
                "estado": "Anulado",
                "tipo_factura": "ANULACION",
                "observaciones": "ANULADA por {} | Motivo: {}".format(usuario, motivo),
                "bloqueado": True,
            }).eq("id", factura_id).execute()
            self.registrar_auditoria("ANULAR_FACTURA", "presupuestos", factura_id, {
                "num_factura": factura["num_factura"],
                "usuario": usuario,
                "motivo": motivo,
            })
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def crear_factura_rectificativa(self, factura_origen_id, empresa_id, cambios):
        try:
            res = self.db.table("presupuestos").select("*").eq("id", factura_origen_id).execute()
            if not res.data:
                return {"success": False, "error": "Factura original no encontrada"}
            factura_original = res.data[0]
            num_secuencial = self.obtener_numero_secuencial(empresa_id)
            if not num_secuencial:
                return {"success": False, "error": "Error generando numero secuencial"}
            anio = datetime.date.today().year
            num_factura_rect = "RECT-{}-{:06d}".format(anio, num_secuencial)
            nif_empresa = factura_original.get("nif_empresa")
            if not nif_empresa:
                res_emp = self.db.table("empresas").select("nif").eq("id", empresa_id).single().execute()
                nif_empresa = res_emp.data.get("nif", "") if res_emp.data else ""
            hash_anterior = self.obtener_hash_anterior(empresa_id)
            nuevo_total = float(cambios["total"])
            total_neto = cambios.get("total_neto", nuevo_total / 1.21)
            impuestos = cambios.get("impuestos", nuevo_total - total_neto)
            datos_hash = {
                "nif_empresa": nif_empresa,
                "nif_cliente": cambios.get("nif_cliente", ""),
                "num_factura": num_factura_rect,
                "fecha": str(datetime.date.today()),
                "total": nuevo_total,
            }
            hash_rect = self.generar_hash_factura(datos_hash, hash_anterior)
            self.db.table("presupuestos").insert({
                "empresa_id": empresa_id,
                "cliente": cambios.get("cliente", factura_original["cliente"]),
                "nif_cliente": cambios.get("nif_cliente", factura_original.get("nif_cliente")),
                "titulo": "RECTIFICATIVA de {}".format(factura_original.get("num_factura", "N/A")),
                "total_neto": round(total_neto, 2),
                "impuestos": round(impuestos, 2),
                "total_final": nuevo_total,
                "iva_porcentaje": factura_original.get("iva_porcentaje", 21.0),
                "moneda": factura_original.get("moneda", "EUR"),
                "estado": "Facturado",
                "tipo_factura": "RECTIFICATIVA",
                "num_factura": num_factura_rect,
                "numero_secuencial": num_secuencial,
                "fecha": str(datetime.date.today()),
                "fecha_factura": str(datetime.date.today()),
                "hash_factura": hash_rect,
                "hash_anterior": hash_anterior,
                "nif_empresa": nif_empresa,
                "observaciones": "Rectificativa de {} | {}".format(
                    factura_original.get("num_factura"), cambios.get("motivo", "")
                ),
                "bloqueado": True,
                "items": factura_original.get("items", "[]"),
            }).execute()
            self.db.table("presupuestos").update({
                "observaciones": "RECTIFICADA por {}".format(num_factura_rect)
            }).eq("id", factura_origen_id).execute()
            self.registrar_auditoria("CREAR_FACTURA_RECTIFICATIVA", "presupuestos", factura_origen_id, {
                "num_factura_rect": num_factura_rect,
                "hash": hash_rect[:16] + "...",
                "factura_origen": factura_original.get("num_factura"),
            })
            return {"success": True, "num_factura": num_factura_rect, "hash": hash_rect}
        except Exception as e:
            return {"success": False, "error": str(e)}
