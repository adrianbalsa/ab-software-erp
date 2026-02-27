from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import streamlit as st
import datetime
import re


class AzureService:
    @staticmethod
    def get_client():
        endpoint = st.secrets.get("AZURE_ENDPOINT")
        key = st.secrets.get("AZURE_KEY")

        if not endpoint or not key:
            return None
        return DocumentAnalysisClient(endpoint, AzureKeyCredential(key))

    @staticmethod
    def limpiar_precio(texto_precio):
        """Limpia símbolos de moneda y espacios para convertir a float correctamente."""
        if not texto_precio: return 0.0
        try:
            # Quitamos todo lo que no sea numero, punto o coma
            limpio = re.sub(r'[^\d.,]', '', str(texto_precio))
            # Reemplazamos coma por punto si es decimal europeo
            limpio = limpio.replace(',', '.')
            return float(limpio)
        except:
            return 0.0

    @staticmethod
    def analizar_ticket(archivo_bytes):
        client = AzureService.get_client()
        if not client:
            st.warning("⚠️ OCR no disponible: Faltan claves Azure en secrets.toml. Modo manual activado.")
            return {}

        try:
            archivo_bytes.seek(0)  # Asegurar lectura desde el inicio
            poller = client.begin_analyze_document("prebuilt-invoice", document=archivo_bytes)
            result = poller.result()

            if not result.documents:
                return {}

            invoice = result.documents[0]
            fields = invoice.fields

            # 1. Extracción Proveedor
            prov_field = fields.get("VendorName")
            prov = prov_field.value if prov_field else ""

            # 2. Extracción Fecha
            date_field = fields.get("InvoiceDate")
            fecha = date_field.value if date_field else datetime.date.today()

            # 3. Extracción Inteligente de Total
            # Primero intentamos los campos estándar
            total_field = fields.get("InvoiceTotal") or fields.get("AmountDue")

            if total_field and total_field.value:
                total_val = float(total_field.value)
            else:
                # ESTRATEGIA DE RESPALDO: Buscar en los Items si el total falla
                # A veces Azure detecta los items pero no el total en tickets simplificados
                suma_items = 0.0
                items = fields.get("Items")
                if items and items.value:
                    for item in items.value:
                        item_val = item.value
                        if "Amount" in item_val and item_val["Amount"].value:
                            suma_items += float(item_val["Amount"].value)
                total_val = suma_items

            # 4. Descripción / Concepto
            concepto = "Gasto Varios"
            items = fields.get("Items")
            if items and items.value:
                try:
                    # Cogemos la descripción del primer item que tenga texto
                    for it in items.value:
                        desc_field = it.value.get("Description")
                        if desc_field and desc_field.value:
                            concepto = desc_field.value
                            break
                except:
                    pass

            # Si aún así el concepto es genérico y tenemos proveedor, usamos el proveedor
            if concepto == "Gasto Varios" and prov:
                concepto = f"Compra en {prov}"

            return {
                "Fecha": fecha,
                "Proveedor": str(prov).upper(),
                "Total_CHF": total_val,
                "Concepto": str(concepto).upper()
            }

        except Exception as e:
            st.error(f"Error de conexión con IA: {e}")
            return {}