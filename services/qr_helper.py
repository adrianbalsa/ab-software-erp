import qrcode
from io import BytesIO
from PIL import Image


class QRHelper:
    """
    Servicio para generar códigos QR de facturas Verifactu
    """

    @staticmethod
    def generar_qr_factura(num_factura, hash_factura, dominio="https://absoftware.es"):
        """
        Genera código QR con URL verificación pública.

        Parámetros:
        - num_factura: FAC-2026-000001
        - hash_factura: hash SHA-256 completo
        - dominio: URL base app (cambiar antes producción)

        Retorna:
        - Imagen PIL (bytes) lista para insertar en PDF
        """
        try:
            # URL verificación pública
            url = f"{dominio}/verify?num={num_factura}&hash={hash_factura}"

            # Configurar QR
            qr = qrcode.QRCode(
                version=1,  # Tamaño automático
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # Alta corrección (30%)
                box_size=3,  # Tamaño pixel
                border=1,  # Borde mínimo
            )

            qr.add_data(url)
            qr.make(fit=True)

            # Generar imagen
            img = qr.make_image(fill_color="black", back_color="white")

            # Convertir a bytes para PDF
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            return buffer

        except Exception as e:
            print(f"Error generando QR: {e}")
            return None

    @staticmethod
    def validar_url_verificacion(url):
        """
        Valida que la URL de verificación sea correcta.
        """
        return "verify" in url and "hash=" in url
