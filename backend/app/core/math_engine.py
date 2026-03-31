"""
Motor de precisión financiera: ``decimal`` exclusivo, redondeo contable (HALF_EVEN)
a 2 decimales (EUR), división segura y validaciones de dominio.

La clase :class:`MathEngine` usa **ROUND_HALF_EVEN** (redondeo bancario) y cuantía **0,01 €**,
alineada con ``numeric(12,2)`` en PostgreSQL/Supabase.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    InvalidOperation,
    localcontext,
)
from typing import Any

FIAT_QUANT = Decimal("0.01")

# Contexto financiero: precisión amplia y redondeo HALF_EVEN al cuantificar a céntimos.
_MATH_CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)


class FinancialDomainError(ValueError):
    """Dato monetario inválido (p. ej. precio negativo donde no aplica). Las rutas API suelen mapearlo a 400."""


class RoundingIntegrityError(FinancialDomainError):
    """Descuadre contable tras redondeo (total != base + IVA [+ RE])."""


def to_decimal(value: float | str | Decimal | None) -> Decimal:
    """Convierte entrada a ``Decimal`` sin pasar por binarios de ``float`` cuando es posible."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return Decimal("0")
        try:
            return Decimal(s)
        except InvalidOperation as e:
            raise FinancialDomainError(f"Importe no numérico: {value!r}") from e
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as e:
        raise FinancialDomainError(f"Importe no numérico: {value!r}") from e


def quantize_currency(value: Decimal) -> Decimal:
    """
    Cuantiza un Decimal a **2 decimales** exactos (EUR) con ``ROUND_HALF_EVEN``.
    """
    with localcontext(_MATH_CTX):
        return value.quantize(FIAT_QUANT, rounding=ROUND_HALF_EVEN)


def round_fiat(value: float | str | Decimal | None) -> Decimal:
    """
    Redondeo contable a **2 decimales** exactos (EUR) con ``ROUND_HALF_EVEN``.
    """
    try:
        d = to_decimal(value)
    except FinancialDomainError:
        raise
    except Exception as e:
        raise FinancialDomainError(f"No se pudo interpretar el importe: {value!r}") from e
    return quantize_currency(d)


def as_float_fiat(value: float | str | Decimal | None) -> float:
    """Serialización API / JSON: ``float`` con exactamente la semántica ``round_fiat``."""
    return float(round_fiat(value))


def safe_divide(
    numerator: float | str | Decimal | None,
    denominator: float | str | Decimal | None,
) -> Decimal:
    """
    Cociente en fiat; si el denominador es 0 o nulo, devuelve ``Decimal('0.00')``
    (evita ``ZeroDivisionError`` en ratios operativos: km, bultos, etc.).
    """
    n = round_fiat(numerator)
    if denominator is None:
        return Decimal("0.00")
    d = to_decimal(denominator)
    if d == 0:
        return Decimal("0.00")
    return round_fiat(n / d)


def require_non_negative_precio_pactado(portes_rows: list[dict[str, Any]]) -> None:
    """Facturación: ninguna línea puede traer ``precio_pactado`` negativo."""
    for r in portes_rows:
        raw = r.get("precio_pactado")
        try:
            v = round_fiat(raw)
        except FinancialDomainError:
            raise
        if v < 0:
            raise FinancialDomainError(
                "precio_pactado no puede ser negativo en la emisión de factura (línea de porte)."
            )


def assert_non_negative_fiat(name: str, value: float | str | Decimal | None) -> None:
    """Validación genérica de importes que deben ser ≥ 0 (precio oferta, bases, etc.)."""
    v = round_fiat(value)
    if v < 0:
        raise FinancialDomainError(f"{name} no puede ser negativo.")


def sum_precios_pactados(portes_rows: list[dict[str, Any]]) -> Decimal:
    """Suma de precios pactados en Decimal (previo a ``round_fiat`` de la base)."""
    acc = Decimal("0")
    for r in portes_rows:
        acc += to_decimal(r.get("precio_pactado") or 0)
    return acc


def compute_f1_totals(*, base_imponible: Decimal, iva_porcentaje: float | Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Base + cuota IVA + total con redondeo fiat en cada paso.
    ``iva_porcentaje`` es el tanto por ciento (p. ej. 21).
    """
    base = quantize_currency(to_decimal(base_imponible))
    pct = to_decimal(iva_porcentaje)
    cuota = quantize_currency(base * (pct / Decimal("100")))
    total = quantize_currency(base + cuota)
    return base, cuota, total


def negate_fiat_for_rectificativa(value: Any) -> Decimal:
    """
    Importe positivo de una F1 → negativo para R1, siempre en cuantía fiat.
    """
    v = round_fiat(value or 0)
    if v == 0:
        return Decimal("0.00")
    return round_fiat(-abs(v))


def quantize_financial(value: float | str | Decimal | None) -> Decimal:
    """Cuantía a 2 decimales con **ROUND_HALF_EVEN** (contabilidad / MathEngine)."""
    try:
        d = to_decimal(value)
    except FinancialDomainError:
        raise
    except Exception as e:
        raise FinancialDomainError(f"No se pudo interpretar el importe: {value!r}") from e
    return quantize_currency(d)


def decimal_to_db_numeric(value: Decimal) -> Decimal:
    """
    Salida estable para columnas ``numeric(12,2)``: siempre 2 decimales, HALF_UP.
    """
    return quantize_currency(value)


# Recargo de equivalencia (sobre base imponible del grupo) — tipos generales AEAT habituales.
RECARGO_EQUIVALENCIA_POR_IVA_PCT: dict[str, Decimal] = {
    "21.00": Decimal("5.20"),
    "10.00": Decimal("1.40"),
    "4.00": Decimal("0.50"),
    "0.00": Decimal("0.00"),
}


def _iva_rate_key(pct: Decimal) -> str:
    with localcontext(_MATH_CTX):
        return str(pct.quantize(FIAT_QUANT, rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True, slots=True)
class LineaTotalCalculada:
    """Línea tras cálculo (base imponible de línea en EUR)."""

    indice: int
    cantidad: Decimal
    precio_unitario: Decimal
    base_imponible: Decimal
    tipo_iva_porcentaje: Decimal
    descuento_linea: Decimal


@dataclass(frozen=True, slots=True)
class DesgloseTipoIva:
    tipo_iva_porcentaje: Decimal
    base_imponible: Decimal
    cuota_iva: Decimal
    cuota_recargo_equivalencia: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceTotalsResult:
    """Totales factura coherentes Base + IVA (+ recargo equivalencia opcional)."""

    base_imponible_total: Decimal
    cuota_iva_total: Decimal
    cuota_recargo_equivalencia_total: Decimal
    total_factura: Decimal
    desglose_por_tipo: tuple[DesgloseTipoIva, ...]
    lineas: tuple[LineaTotalCalculada, ...]
    ajuste_centimos: Decimal = Decimal("0.00")
    importe_descuento_global_aplicado: Decimal = Decimal("0.00")


class MathEngine:
    """
    Cálculos **exclusivamente** con :class:`decimal.Decimal` y redondeo **ROUND_HALF_EVEN**
    a céntimos, para cuadrar base, IVA y total sin deriva.
    """

    @staticmethod
    def calculate_totals(
        items: list[dict[str, Any]],
        global_discount: Decimal = Decimal("0"),
        *,
        aplicar_recargo_equivalencia: bool = False,
        allow_negative_bases: bool = False,
    ) -> InvoiceTotalsResult:
        """
        - Base imponible **línea a línea** (cantidad × precio − descuento de línea), cuantizada.
        - Agrupación por tipo de IVA (21 %, 10 %, 4 %, …).
        - Cuota IVA por grupo: ``quantize(base_grupo × tipo/100)``.
        - Recargo de equivalencia opcional por grupo según :data:`RECARGO_EQUIVALENCIA_POR_IVA_PCT`.
        - **Consistencia céntimo**: ``total = base + IVA + RE``; si hiciera falta un ajuste de
          0,01 € por artefactos de reparto de descuento global, se corrige en la línea de mayor importe.

        Cada ítem admite claves flexibles:

        - ``cantidad`` / ``qty`` (defecto 1),
        - ``precio_unitario`` / ``precio_pactado`` / ``unit_price``,
        - ``tipo_iva_porcentaje`` / ``iva_porcentaje`` / ``iva_pct``,
        - ``descuento_linea`` (opcional, en EUR),
        - ``recargo_equivalencia`` (opcional, ``bool`` por línea; si no, usa ``aplicar_recargo_equivalencia``).
        """
        with localcontext(_MATH_CTX):
            disc_glob = quantize_financial(global_discount)
            if disc_glob < 0:
                raise FinancialDomainError("El descuento global no puede ser negativo.")

            if not items:
                raise FinancialDomainError("Sin líneas de factura.")

            line_nets: list[Decimal] = []
            meta: list[tuple[Decimal, Decimal, bool]] = []
            # (iva_pct, desc_line, rec_line_flag) por línea
            for idx, raw in enumerate(items):
                qty = quantize_financial(
                    raw.get("cantidad") if raw.get("cantidad") is not None else raw.get("qty") or 1
                )
                if qty < 0:
                    raise FinancialDomainError(f"Línea {idx}: cantidad no puede ser negativa.")
                price = to_decimal(
                    raw.get("precio_unitario")
                    if raw.get("precio_unitario") is not None
                    else raw.get("precio_pactado")
                    if raw.get("precio_pactado") is not None
                    else raw.get("unit_price")
                    if raw.get("unit_price") is not None
                    else 0
                )
                d_line = quantize_financial(raw.get("descuento_linea") or 0)
                if d_line < 0:
                    raise FinancialDomainError(f"Línea {idx}: descuento_linea no puede ser negativo.")
                raw_iva = raw.get("tipo_iva_porcentaje")
                if raw_iva is None:
                    raw_iva = raw.get("iva_porcentaje")
                if raw_iva is None:
                    raw_iva = raw.get("iva_pct")
                if raw_iva is None:
                    raw_iva = Decimal("0")
                iva_pct = quantize_financial(raw_iva)
                if iva_pct < 0 or iva_pct > Decimal("100"):
                    raise FinancialDomainError(f"Línea {idx}: tipo IVA fuera de rango.")

                bruto = quantize_financial(qty * price)
                net = quantize_financial(bruto - d_line)
                if net < 0 and not allow_negative_bases:
                    raise FinancialDomainError(f"Línea {idx}: importe neto negativo tras descuentos.")
                re_flag = bool(raw.get("recargo_equivalencia")) if raw.get("recargo_equivalencia") is not None else aplicar_recargo_equivalencia

                line_nets.append(net)
                meta.append((iva_pct, d_line, re_flag))

            # Importe cero (pro-bono / muestras): todo ceros coherentes
            total_net = quantize_financial(sum(line_nets, start=Decimal("0")))
            if total_net == 0:
                zlines = tuple(
                    LineaTotalCalculada(
                        indice=i,
                        cantidad=quantize_financial(items[i].get("cantidad") or items[i].get("qty") or 1),
                        precio_unitario=quantize_financial(
                            items[i].get("precio_unitario")
                            or items[i].get("precio_pactado")
                            or items[i].get("unit_price")
                            or 0
                        ),
                        base_imponible=Decimal("0.00"),
                        tipo_iva_porcentaje=meta[i][0],
                        descuento_linea=meta[i][1],
                    )
                    for i in range(len(items))
                )
                return InvoiceTotalsResult(
                    base_imponible_total=Decimal("0.00"),
                    cuota_iva_total=Decimal("0.00"),
                    cuota_recargo_equivalencia_total=Decimal("0.00"),
                    total_factura=Decimal("0.00"),
                    desglose_por_tipo=tuple(),
                    lineas=zlines,
                    ajuste_centimos=Decimal("0.00"),
                    importe_descuento_global_aplicado=Decimal("0.00"),
                )

            if not allow_negative_bases and disc_glob > total_net:
                raise FinancialDomainError("Descuento global superior a la base imponible bruta.")
            if allow_negative_bases and disc_glob != Decimal("0.00"):
                raise FinancialDomainError(
                    "No se admite descuento global en cálculo con bases negativas (rectificativa)."
                )

            # Reparto proporcional del descuento global con corrección de céntimo en la línea mayor
            if disc_glob == 0:
                adjusted = list(line_nets)
                disc_applied = Decimal("0.00")
            else:
                target = quantize_financial(total_net - disc_glob)
                factor = target / total_net
                adjusted = [quantize_financial(ln * factor) for ln in line_nets]
                drift = target - sum(adjusted, start=Decimal("0"))
                if drift != 0 and adjusted:
                    j = max(range(len(adjusted)), key=lambda k: adjusted[k])
                    adjusted[j] = quantize_financial(adjusted[j] + drift)
                disc_applied = quantize_financial(total_net - target)

            # Agrupar bases por tipo IVA
            buckets: dict[str, Decimal] = {}
            cuotas_buckets: dict[str, Decimal] = {}
            re_for_bucket: dict[str, bool] = {}
            line_results: list[LineaTotalCalculada] = []

            for i, adj in enumerate(adjusted):
                iva_pct, d_line, re_f = meta[i]
                key = _iva_rate_key(iva_pct)
                buckets[key] = buckets.get(key, Decimal("0")) + adj
                # IVA por línea (ROUND_HALF_EVEN) y agregado por tipo.
                line_vat = quantize_financial(adj * (iva_pct / Decimal("100")))
                cuotas_buckets[key] = cuotas_buckets.get(key, Decimal("0")) + line_vat
                # RE por grupo: True si alguna línea del grupo lo pide
                re_for_bucket[key] = re_for_bucket.get(key, False) or re_f
                raw_it = items[i]
                qty_disp = quantize_financial(
                    raw_it.get("cantidad") if raw_it.get("cantidad") is not None else raw_it.get("qty") or 1
                )
                p_disp = quantize_financial(
                    raw_it.get("precio_unitario")
                    or raw_it.get("precio_pactado")
                    or raw_it.get("unit_price")
                    or 0
                )
                line_results.append(
                    LineaTotalCalculada(
                        indice=i,
                        cantidad=qty_disp,
                        precio_unitario=p_disp,
                        base_imponible=adj,
                        tipo_iva_porcentaje=iva_pct,
                        descuento_linea=d_line,
                    )
                )

            base_total = Decimal("0")
            desglose_list: list[DesgloseTipoIva] = []
            cuota_sum = Decimal("0")
            re_sum = Decimal("0")

            for key, raw_base in sorted(buckets.items(), key=lambda x: x[0]):
                b_g = quantize_financial(raw_base)
                base_total += b_g
                iva_pct = Decimal(key)
                cuota = quantize_financial(cuotas_buckets.get(key, Decimal("0.00")))
                re_pct_stat = RECARGO_EQUIVALENCIA_POR_IVA_PCT.get(key, Decimal("0.00"))
                re_cuota = (
                    quantize_financial(b_g * (re_pct_stat / Decimal("100")))
                    if re_for_bucket.get(key, False)
                    else Decimal("0.00")
                )
                cuota_sum += cuota
                re_sum += re_cuota
                desglose_list.append(
                    DesgloseTipoIva(
                        tipo_iva_porcentaje=iva_pct,
                        base_imponible=b_g,
                        cuota_iva=cuota,
                        cuota_recargo_equivalencia=re_cuota,
                    )
                )

            base_total = quantize_financial(base_total)
            cuota_sum = quantize_financial(cuota_sum)
            re_sum = quantize_financial(re_sum)
            merged = quantize_financial(base_total + cuota_sum + re_sum)
            # Coherencia: total = base + IVA + RE (misma cuantía)
            ajuste = Decimal("0.00")
            check = abs(merged - (base_total + cuota_sum + re_sum))
            if check >= Decimal("0.001"):
                raise RoundingIntegrityError(
                    "Rounding integrity check failed: abs(total - (base + iva + re)) >= 0.001"
                )

            return InvoiceTotalsResult(
                base_imponible_total=decimal_to_db_numeric(base_total),
                cuota_iva_total=decimal_to_db_numeric(cuota_sum),
                cuota_recargo_equivalencia_total=decimal_to_db_numeric(re_sum),
                total_factura=decimal_to_db_numeric(merged),
                desglose_por_tipo=tuple(desglose_list),
                lineas=tuple(line_results),
                ajuste_centimos=decimal_to_db_numeric(ajuste),
                importe_descuento_global_aplicado=decimal_to_db_numeric(disc_applied),
            )

    @staticmethod
    def calculate_invoice_totals(
        items: list[dict[str, Any]],
        global_discount: Decimal = Decimal("0"),
        *,
        aplicar_recargo_equivalencia: bool = False,
        allow_negative_bases: bool = False,
    ) -> InvoiceTotalsResult:
        """
        Alias explícito para facturación: soporta rectificativas con bases negativas.
        """
        return MathEngine.calculate_totals(
            items,
            global_discount=global_discount,
            aplicar_recargo_equivalencia=aplicar_recargo_equivalencia,
            allow_negative_bases=allow_negative_bases,
        )
