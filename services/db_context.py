import streamlit as st


class DBContext:
    """
    Wrapper que inyecta el contexto de empresa antes de cada operación.
    Usar en lugar de `db` directamente cuando RLS está activo.
    """

    def __init__(self, db_client):
        self._db = db_client

    def _set_context(self):
        empresa_id = (
            st.session_state.get("empresa_id")
            or st.session_state.get("empresaid")
        )
        if empresa_id:
            try:
                self._db.rpc(
                    "set_empresa_context",
                    {"p_empresa_id": str(empresa_id)}
                ).execute()
            except Exception:
                pass

    def table(self, name: str):
        self._set_context()
        return self._db.table(name)

    def rpc(self, fn: str, params: dict = None):
        self._set_context()
        return self._db.rpc(fn, params or {})
