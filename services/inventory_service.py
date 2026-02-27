# services/inventory_service.py
import streamlit as st

class InventoryService:
    def __init__(self, db_client):
        self.db = db_client

    def obtener_todo(self):
        """Descarga todo el inventario para mostrarlo."""
        response = self.db.table("inventario").select("*").order("nombre").execute()
        return response.data

    def crear_item(self, datos):
        """Crea una herramienta o material nuevo."""
        try:
            self.db.table("inventario").insert(datos).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def actualizar_stock(self, id_item, nuevo_stock):
        """Cambia la cantidad (Suma/Resta)."""
        try:
            self.db.table("inventario").update({"stock": nuevo_stock}).eq("id", id_item).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def registrar_movimiento(self, id_item, nueva_ubicacion, nuevo_responsable, estado="En Uso"):
        """
        TRAZABILIDAD: Mueve una herramienta de un sitio a otro.
        Si vuelve al almacén, el responsable se limpia.
        """
        try:
            payload = {
                "ubicacion": nueva_ubicacion,
                "responsable": nuevo_responsable,
                "estado": estado
            }
            self.db.table("inventario").update(payload).eq("id", id_item).execute()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}