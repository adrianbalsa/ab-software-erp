from app.core.esg_engine import calculate_co2_emissions, resolve_normativa_euro_for_co2


def test_calculate_co2_emissions_euro_steps() -> None:
    km = 100.0
    assert calculate_co2_emissions(km, "Euro VI") == round(km * 0.62, 6)
    assert calculate_co2_emissions(km, "Euro V") == round(km * 0.68, 6)
    assert calculate_co2_emissions(km, "Euro IV") == round(km * 0.74, 6)


def test_resolve_normativa_prioriza_columna_dedicada() -> None:
    assert (
        resolve_normativa_euro_for_co2(
            normativa_euro="Euro IV",
            certificacion_emisiones="Euro VI",
        )
        == "Euro IV"
    )


def test_resolve_normativa_desde_certificacion() -> None:
    assert resolve_normativa_euro_for_co2(certificacion_emisiones="Euro V") == "Euro V"
    assert resolve_normativa_euro_for_co2(certificacion_emisiones="Electrico") == "Euro VI"
