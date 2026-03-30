from pydantic import BaseModel, Field

class TruckEfficiencyOut(BaseModel):
    matricula: str = Field(..., description="Matrícula del vehículo", examples=["1234ABC"])
    marca_modelo: str = Field(..., description="Marca y modelo del vehículo", examples=["Scania R500"])
    km_totales: float = Field(..., ge=0, description="Kilómetros recorridos en el periodo", examples=[12500.0])
    litros_totales: float = Field(..., ge=0, description="Litros de combustible consumidos", examples=[3500.0])
    consumo_medio: float = Field(..., ge=0, description="Consumo medio en litros por cada 100km", examples=[28.0])
    coste_por_km: float = Field(..., ge=0, description="Coste operativo total por kilómetro (EUR)", examples=[1.15])
    alerta_mantenimiento: bool = Field(..., description="Verdadero si el vehículo requiere mantenimiento pronto", examples=[False])
    margen_generado: float = Field(..., description="Margen económico generado por el vehículo (EUR)", examples=[4200.50])
