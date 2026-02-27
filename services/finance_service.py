# services/finance_service.py
import streamlit as st
from datetime import date


class FinanceService:
    def __init__(self, db_client):
        self.db = db_client

    def obtener_categorias(self):
        """
        Devuelve la lista de categorías permitidas.
        En el futuro esto podría venir de la base de datos.
        """
        return [
            "Material", "Combustible", "Dietas",
            "Herramienta", "Vehículo Mantenimiento",
            "Oficina/Admin", "Seguros", "Otros"
        ]

    def registrar_gasto(self, datos_gasto: dict):
        """
        Recibe un diccionario con los datos y los guarda en Supabase (SQL).
        """
        try:
            # 1. Validaciones de Negocio (Business Logic)
            if datos_gasto["total"] < 0:
                return {"success": False, "error": "El importe no puede ser negativo"}

            if not datos_gasto["empleado"]:
                return {"success": False, "error": "El gasto debe tener un empleado asignado"}

            # 2. Preparar el Payload (Los datos exactos para la tabla SQL)
            # NOTA: Usamos un ID de empresa fijo por ahora hasta que tengamos el Login listo.
            payload = {
                "empresa_id": st.session_state.get("empresa_id", "empresa_demo_01"),
                "fecha": str(datos_gasto["fecha"]),
                "empleado": datos_gasto["empleado"],
                "categoria": datos_gasto["categoria"],
                "proveedor": datos_gasto["proveedor"],
                "total_chf": float(datos_gasto["total"]),
                "proyecto": datos_gasto["proyecto"],
                "notas": datos_gasto.get("notas", "")
                # "url_foto": ... (Lo implementaremos cuando conectemos el Storage)
            }

            # 3. Insertar en Base de Datos
            response = self.db.table("gastos").insert(payload).execute()

            return {"success": True, "data": response.data}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def obtener_resumen_mensual(self, mes, anio):
        """
        Obtiene los gastos filtrados para el Dashboard.
        """
        try:
            # Rango de fechas
            fecha_inicio = f"{anio}-{mes:02d}-01"
            # Truco rápido para fin de mes (simplificado)
            fecha_fin = f"{anio}-{mes:02d}-31"

            # Consulta SQL via Supabase
            response = self.db.table("gastos").select("*") \
                .gte("fecha", fecha_inicio) \
                .lte("fecha", fecha_fin) \
                .execute()

            return response.data
        except Exception as e:
            st.error(f"Error recuperando gastos: {e}")
            return []