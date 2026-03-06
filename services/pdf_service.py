from fpdf import FPDF
import datetime
import os

class InvoicePDF(FPDF):
    def header(self):
        # 1. Inyección del Logo a la izquierda (si existe)
        ruta_logo = "assets/logo.png"
        if os.path.exists(ruta_logo):
            # Posicionamos el logo: x=10, y=8, ancho=35mm
            self.image(ruta_logo, x=10, y=8, w=35)
            
        # 2. Textos de la cabecera a la derecha
        self.set_y(10) # Alineamos la altura
        self.set_font('Arial', 'B', 15)
        self.set_text_color(16, 42, 67) # Color corporativo NAVY
        self.cell(0, 10, 'FACTURA OFICIAL', 0, 1, 'R')
        
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 100, 100) # Gris elegante para la fecha
        self.cell(0, 5, f'Fecha: {datetime.date.today()}', 0, 1, 'R')
        self.ln(15) # Salto de línea para separar de los datos

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_factura(datos_empresa, datos_cliente, conceptos):
    pdf = InvoicePDF()
    pdf.add_page()
    
    # Datos Emisor (Tú)
    pdf.set_text_color(16, 42, 67) # Títulos en Navy
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'EMISOR:', 0, 1)
    
    pdf.set_text_color(0, 0, 0) # Texto normal en negro
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Nombre: {datos_empresa['nombre']}", 0, 1)
    pdf.cell(0, 5, f"NIF: {datos_empresa['nif']}", 0, 1)
    pdf.ln(5)

    # Datos Receptor (Cliente)
    pdf.set_text_color(16, 42, 67) # Títulos en Navy
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'CLIENTE:', 0, 1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Empresa: {datos_cliente['nombre']}", 0, 1)
    pdf.cell(0, 5, f"ID Cliente: {datos_cliente['id']}", 0, 1)
    pdf.ln(10)

    # Tabla de Conceptos (Cabecera Corporativa)
    pdf.set_fill_color(16, 42, 67) # Fondo Navy corporativo
    pdf.set_text_color(255, 255, 255) # Texto blanco
    pdf.set_draw_color(16, 42, 67) # Bordes Navy
    pdf.cell(120, 10, 'Concepto', 1, 0, 'C', True)
    pdf.cell(70, 10, 'Total (inc. IVA)', 1, 1, 'C', True)
    
    # Filas de la tabla
    pdf.set_text_color(0, 0, 0) # Devolvemos el texto a negro
    for item in conceptos:
        pdf.cell(120, 10, item['nombre'], 1)
        pdf.cell(70, 10, f"{item['precio']} EUR", 1, 1, 'R')

    # Firma VeriFactu
    pdf.ln(20)
    pdf.set_font('Courier', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, f"Huella Digital VeriFactu: {datos_empresa.get('hash', 'PENDIENTE_VALIDACION_AEAT')}")
    
    return pdf.output(dest='S').encode('latin-1')