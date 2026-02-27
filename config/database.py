import streamlit as st
from supabase import create_client, Client
import os

class Database:
    """
    Clase Singleton para gestión de conexión a Supabase.
    Manejo robusto de errores de configuración.
    """
    def __init__(self):
        # Intentamos obtener secretos de st.secrets o variables de entorno
        self.url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
        self.key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            st.error("🚨 Error Crítico: No se encontraron las credenciales de Supabase (URL/KEY). Revisa .streamlit/secrets.toml")
            st.stop()

        try:
            self.client: Client = create_client(self.url, self.key)
        except Exception as e:
            st.error(f"🚨 Error conectando con la Base de Datos: {e}")
            st.stop()

    def get_client(self) -> Client:
        return self.client

@st.cache_resource
def get_db_connection() -> Client:
    db_instance = Database()
    return db_instance.get_client()

# Instancia global lista para importar
db = get_db_connection()