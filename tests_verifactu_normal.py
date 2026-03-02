from services.verifactu_service import VerifactuService
import datetime

if __name__ == "__main__":
    presupuesto_ejemplo = {
        "fecha": datetime.date.today(),
        "total_neto": 1000,
        "impuestos": 210,
        "total_final": 1210,
    }

    factura1 = VerifactuService.emitir_factura_desde_presupuesto(
        presupuesto_row=presupuesto_ejemplo,
        numero_secuencial=1,
        hash_anterior=None,
        prefijo_serie="A",
        nif_emisor="B12345678",
    )
    factura2 = VerifactuService.emitir_factura_desde_presupuesto(
        presupuesto_row=presupuesto_ejemplo,
        numero_secuencial=2,
        hash_anterior=factura1["hash_factura"],
        prefijo_serie="A",
        nif_emisor="B12345678",
    )

    print("Factura 1:", factura1["num_factura"], factura1["hash_factura"])
    print("Factura 2:", factura2["num_factura"], factura2["hash_factura"])
