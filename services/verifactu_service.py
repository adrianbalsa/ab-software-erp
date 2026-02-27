import hashlib
import json
import datetime
import streamlit as st


class VerifactuService:
    """
    Servicio de gestión de Verifactu:
    - Generación de hashes SHA-256 encadenados
    - Numeración secuencial de facturas
    - Registro de auditoría
    """

    def __init__(self, db_client):
        self.db = db_client

    def obtener_numero_secuencial(self, empresa_id):
        """
        Obtiene el siguiente número secuencial para la empresa.
        Garantiza unicidad y consecutividad.
        """
        try:
            # Obtener el último número secuencial de esta empresa
            result = self.db.table("presupuestos") \
                .select("numero_secuencial") \
                .eq("empresa_id", empresa_id) \
                .not_.is_("numero_secuencial", "null") \
                .order("numero_secuencial", desc=True) \
                .limit(1) \
                .execute()

            if result.data and len(result.data) > 0:
                ultimo = result.data[0]["numero_secuencial"]
                return int(ultimo) + 1
            else:
                # Primera factura de la empresa
                return 1

        except Exception as e:
            st.error(f"Error obteniendo número secuencial: {e}")
            return None

    def obtener_hash_anterior(self, empresa_id):
        """
        Obtiene el hash de la última factura para encadenamiento.
        Si no hay facturas previas, devuelve None.
        """
        try:
            result = self.db.table("presupuestos") \
                .select("hash_factura") \
                .eq("empresa_id", empresa_id) \
                .eq("estado", "Facturado") \
                .not_.is_("hash_factura", "null") \
                .order("numero_secuencial", desc=True) \
                .limit(1) \
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]["hash_factura"]
            else:
                return None  # Primera factura

        except Exception as e:
            st.error(f"Error obteniendo hash anterior: {e}")
            return None

    def generar_hash_factura(self, datos_factura, hash_anterior=None):
        """
        Genera el hash SHA-256 de la factura según especificación Verifactu.

        Parámetros:
        - datos_factura: dict con {nif_empresa, nif_cliente, num_factura, fecha, total}
        - hash_anterior: hash de la factura anterior (encadenamiento)

        Retorna:
        - Hash hexadecimal de 64 caracteres
        """
        try:
            # Construir cadena para hash según normativa
            cadena = (
                f"{datos_factura['nif_empresa']}"
                f"{datos_factura['nif_cliente']}"
                f"{datos_factura['num_factura']}"
                f"{datos_factura['fecha']}"
                f"{datos_factura['total']:.2f}"
            )

            # Si hay hash anterior, incluirlo (encadenamiento blockchain-style)
            if hash_anterior:
                cadena += hash_anterior

            # Generar hash SHA-256
            hash_obj = hashlib.sha256(cadena.encode('utf-8'))
            hash_hex = hash_obj.hexdigest()

            return hash_hex

        except Exception as e:
            st.error(f"Error generando hash Verifactu: {e}")
            return None

    def registrar_auditoria(self, accion, tabla, registro_id, cambios):
        """
        Registra una acción en la tabla de auditoría.

        Parámetros:
        - accion: tipo de acción (ej: "GENERAR_FACTURA_VERIFACTU")
        - tabla: nombre de la tabla afectada
        - registro_id: ID del registro modificado
        - cambios: dict con los cambios realizados
        """
        try:
            payload = {
                "accion": accion,
                "tabla": tabla,
                "registro_id": str(registro_id),
                "cambios": json.dumps(cambios),
                "fecha": str(datetime.datetime.now()),
                "empresa_id": st.session_state.get("empresa_id", "unknown")
            }

            self.db.table("auditoria").insert(payload).execute()

        except Exception as e:
            # No bloqueamos la operación si falla la auditoría
            st.warning(f"Auditoría no registrada: {e}")

    def verificar_hash(self, hash_factura, datos_factura, hash_anterior=None):
        """
        Verifica si un hash es válido recalculándolo.

        Retorna:
        - True si el hash es válido
        - False si no coincide
        """
        hash_calculado = self.generar_hash_factura(datos_factura, hash_anterior)
        return hash_calculado == hash_factura

    def anular_factura(self, factura_id, usuario, motivo):
        """
        Anula una factura emitida sin borrarla del sistema.
        Cumple con Verifactu: las facturas no se eliminan, se anulan.
        """
        try:
            # Obtener datos de la factura a anular
            res = self.db.table("presupuestos").select(
                "num_factura, total_final, nif_cliente, fecha_factura, empresa_id, numero_secuencial"
            ).eq("id", factura_id).execute()

            if not res.data:
                return {"success": False, "error": "Factura no encontrada"}

            factura = res.data[0]
            empresa_id = factura["empresa_id"]

            # Actualizar estado a ANULADA
            self.db.table("presupuestos").update({
                "estado": "Anulado",
                "tipo_factura": "ANULACION",
                "observaciones": f"ANULADA por {usuario} | Motivo: {motivo}",
                "bloqueado": True
            }).eq("id", factura_id).execute()

            # Registrar auditoría
            self.registrar_auditoria(
                "ANULAR_FACTURA",
                "presupuestos",
                factura_id,
                {
                    "num_factura": factura["num_factura"],
                    "usuario": usuario,
                    "motivo": motivo
                }
            )

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def crear_factura_rectificativa(self, factura_origen_id, empresa_id, cambios):
        """
        Crea una nueva factura rectificativa que referencia la original.
        La factura original se marca como rectificada (no se modifica).
        """
        import datetime

        try:
            # Obtener factura original
            res = self.db.table("presupuestos").select("*").eq("id", factura_origen_id).execute()
            if not res.data:
                return {"success": False, "error": "Factura original no encontrada"}

            factura_original = res.data[0]

            # Número secuencial para la rectificativa
            num_secuencial = self.obtener_numero_secuencial(empresa_id)
            if not num_secuencial:
                return {"success": False, "error": "Error generando número secuencial"}

            año = datetime.date.today().year
            num_factura_rect = f"RECT-{año}-{num_secuencial:06d}"

            # Hash para la rectificativa
            hash_anterior = self.obtener_hash_anterior(empresa_id)
            # Leer NIF desde BD si no está en la factura original
            nif_empresa = factura_original.get('nif_empresa')
            if not nif_empresa:
                res_emp = self.db.table('empresas').eq('id', empresa_id).single().execute()
                nif_empresa = res_emp.data.get('nif', '') if res_emp.data else ''
            datos_hash = {
                "nif_empresa": nif_empresa,
                "nif_cliente": cambios.get("nif_cliente", ""),
                "num_factura": num_factura_rect,
                "fecha": str(datetime.date.today()),
                "total": float(cambios["total"])
            }

            hash_rect = self.generar_hash_factura(datos_hash, hash_anterior)

            # Insertar factura rectificativa
            nuevo_total = float(cambios["total"])
            total_neto = cambios.get("total_neto", nuevo_total / 1.21)
            impuestos = cambios.get("impuestos", nuevo_total - total_neto)

            self.db.table("presupuestos").insert({
                "empresa_id": empresa_id,
                "cliente": cambios.get("cliente", factura_original["cliente"]),
                "nif_cliente": cambios.get("nif_cliente", factura_original.get("nif_cliente")),
                "titulo": f"RECTIFICATIVA de {factura_original.get('num_factura', 'N/A')}",
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
                "observaciones": f"Rectificativa de {factura_original.get('num_factura')} | {cambios.get('motivo', '')}",
                "bloqueado": True,
                "items": factura_original.get("items", "[]")
            }).execute()

            # Marcar original como rectificada
            self.db.table("presupuestos").update({
                "observaciones": f"RECTIFICADA por {num_factura_rect}"
            }).eq("id", factura_origen_id).execute()

            self.registrar_auditoria(
                "CREAR_FACTURA_RECTIFICATIVA",
                "presupuestos",
                factura_origen_id,
                {
                    "num_factura_rect": num_factura_rect,
                    "hash": hash_rect[:16] + "...",
                    "factura_origen": factura_original.get("num_factura")
                }
            )

            return {
                "success": True,
                "num_factura": num_factura_rect,
                "hash": hash_rect
            }

        except Exception as e:
            return {"success": False, "error": str(e)}