from __future__ import annotations

from app.services.secret_manager_service import get_secret_manager


def assert_verifactu_genesis_configured_for_production_aeat(settings: object) -> None:
    """
    Arranque en producción con AEAT activo: el hash génesis debe resolverse vía Secret Manager
    (``VERIFACTU_GENESIS_HASH`` / ``VERIFACTU_GENESIS_HASHES`` en env, JSON en Vault/AWS, etc.).
    Con mapa por ``empresa_id``, fijar ``VERIFACTU_GENESIS_STARTUP_ISSUER_ID`` a un UUID válido
    para la sonda al arrancar.
    """
    env = str(getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    aeat_on = bool(getattr(settings, "AEAT_VERIFACTU_ENABLED", False))
    if env != "production" or not aeat_on:
        return
    from os import getenv

    from app.core.config import ConfigError

    probe_issuer = (getenv("VERIFACTU_GENESIS_STARTUP_ISSUER_ID") or "").strip()
    if not probe_issuer:
        probe_issuer = "00000000-0000-0000-0000-000000000001"
    try:
        get_verifactu_genesis_hash_for_issuer(issuer_id=probe_issuer)
    except RuntimeError as exc:
        raise ConfigError(
            "ENVIRONMENT=production con AEAT_VERIFACTU_ENABLED=true requiere hash génesis VeriFactu "
            "accesible antes de aceptar tráfico: configure VERIFACTU_GENESIS_HASH o "
            "VERIFACTU_GENESIS_HASHES (u homólogos en el JSON del secret manager). "
            "Si usa mapa por emisor, defina VERIFACTU_GENESIS_STARTUP_ISSUER_ID con el UUID de una "
            "empresa existente para validar el arranque."
        ) from exc


def get_verifactu_genesis_hash_for_issuer(
    *,
    issuer_id: str,
    issuer_nif: str | None = None,
) -> str:
    """
    Resuelve el hash génesis VeriFactu (SHA-256 hex, 64 caracteres) para un emisor.

    **Origen obligatorio:** ``SecretManagerService`` (``SECRET_MANAGER_BACKEND``: env,
    Vault KV, AWS Secrets Manager, etc.). No existe valor por defecto en código: si no hay
    secreto configurado, se lanza ``RuntimeError('verifactu_genesis_hash_missing_for_issuer')``.

    **Formatos soportados** (misma prioridad que en ``get_verifactu_genesis_hash``):

    - Mapa ``VERIFACTU_GENESIS_HASHES`` / ``VERIFACTU_GENESIS_HASH_BY_EMISOR`` /
      ``VERIFACTU_GENESIS_HASH_BY_ISSUER`` con claves ``empresa_id`` o NIF normalizado
      (mayúsculas, sin espacios) y valores hash hex.
    - Hash único global ``VERIFACTU_GENESIS_HASH`` cuando un solo emisor o entorno
      compartido usa la misma semilla de cadena (menos habitual en multi-tenant).

    La cadena fiscal en BD siempre referencia el hash anterior; el génesis solo aplica
    como ``RegistroAnterior`` lógico para la primera factura del emisor.
    """
    genesis = get_secret_manager().get_verifactu_genesis_hash(
        issuer_id=issuer_id,
        issuer_nif=issuer_nif,
    )
    if not genesis:
        raise RuntimeError("verifactu_genesis_hash_missing_for_issuer")
    return genesis
