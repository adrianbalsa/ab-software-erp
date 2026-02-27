from supabase import Client
import hashlib
import streamlit as st

class AuthService:
    def __init__(self, db_client: Client):
        self.db = db_client

    def login(self, username: str, password: str):
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        try:
            res = self.db.table("usuarios").select("*").eq("username", username).execute()
            rows = res.data or []
        except Exception as e:
            return {"success": False, "error": f"Error consultando usuarios: {e}"}

        if not rows:
            return {"success": False, "error": "Usuario no encontrado"}

        user = rows[0]
        if user.get("password_hash") != password_hash:
            return {"success": False, "error": "Contraseña incorrecta"}

        empresa_id = user.get("empresa_id")
        if not empresa_id:
            return {"success": False, "error": "El usuario no tiene empresa asociada"}

        # MUY IMPORTANTE: fijar contexto en Supabase (RLS)
        try:
            self.db.rpc("set_empresa_context", {"p_empresa_id": empresa_id}).execute()
        except Exception as e:
            st.warning(f"No se pudo fijar el contexto de empresa en Supabase: {e}")

        return {
            "success": True,
            "user": {
                "username": username,
                "empresa_id": empresa_id,
                "rol": user.get("rol", "user"),
            },
        }