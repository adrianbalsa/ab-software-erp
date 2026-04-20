"""Webhook firmado (certificadora externa simulada): cierra ``externally_verified``."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api import deps
from app.services.esg_audit_service import EsgAuditService, verify_esg_external_webhook_signature
from app.services.secret_manager_service import get_secret_manager

router = APIRouter()


@router.post(
    "/esg-external-verify",
    summary="Webhook HMAC: marca certificado como externally_verified",
    status_code=status.HTTP_200_OK,
)
async def post_esg_external_verify_webhook(
    request: Request,
    audit: EsgAuditService = Depends(deps.get_esg_audit_service_admin),
    x_abl_esg_signature: str | None = Header(default=None, alias="X-ABL-ESG-Signature"),
) -> dict[str, Any]:
    secret = (get_secret_manager().get_esg_external_webhook_secret() or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook ESG externo no configurado (ESG_EXTERNAL_WEBHOOK_SECRET).",
        )
    raw = await request.body()
    if not verify_esg_external_webhook_signature(
        secret=secret, raw_body=raw, signature_header=x_abl_esg_signature
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma HMAC inválida",
        )
    try:
        payload = json.loads(raw.decode("utf-8") if raw else b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON inválido",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cuerpo debe ser objeto JSON")
    code = str(payload.get("verification_code") or "").strip()
    if len(code) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="verification_code obligatorio",
        )
    try:
        return await audit.mark_certificate_externally_verified(verification_code=code)
    except ValueError as exc:
        msg = str(exc)
        if "no encontrado" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
