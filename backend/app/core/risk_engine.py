from __future__ import annotations

from typing import Any


class RiskEngine:
    """Motor MVP de evaluacion de riesgo para onboarding B2B."""

    DEFAULT_CREDIT_LIMIT_EUR = 3000
    DEFAULT_COLLECTION_TERMS = "Cobro automatico a 7 dias via SEPA Direct Debit"

    @classmethod
    def calculate_client_risk(cls, cliente: dict[str, Any]) -> dict[str, Any]:
        score = 5
        reasons: list[str] = []

        credit_limit = cls._resolve_credit_limit(cliente)
        has_payment_history = cls._resolve_has_payment_history(cliente)

        if not has_payment_history:
            score += 2
            reasons.append("Cliente sin historial operativo previo")

        if credit_limit > 3000:
            score += 1
            reasons.append("Limite de credito superior al estandar base")

        score = min(10, max(1, score))
        return {
            "score": score,
            "creditLimitEur": credit_limit,
            "collectionTerms": cls.DEFAULT_COLLECTION_TERMS,
            "reasons": reasons,
        }

    @classmethod
    def _resolve_credit_limit(cls, cliente: dict[str, Any]) -> int:
        for key in ("limite_credito", "credit_limit_eur", "credit_limit", "limite"):
            raw = cliente.get(key)
            if raw is None:
                continue
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                continue
        return cls.DEFAULT_CREDIT_LIMIT_EUR

    @classmethod
    def _resolve_has_payment_history(cls, cliente: dict[str, Any]) -> bool:
        for key in ("has_payment_history", "historial_pagos", "tiene_historial_pagos"):
            raw = cliente.get(key)
            if isinstance(raw, bool):
                return raw
            if raw is not None:
                val = str(raw).strip().lower()
                if val in {"1", "true", "si", "yes"}:
                    return True
                if val in {"0", "false", "no"}:
                    return False
        # MVP: sin señal explicita, tratamos al cliente como nuevo.
        return False

