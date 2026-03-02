from fpdf import FPDF
import datetime

class InvoicePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'FACTURA OFICIAL - ERP LOGÍSTICA', 0, 1, 'R')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Fecha: {datetime.date.today()}', 0, 1, 'R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_factura(datos_empresa, datos_cliente, conceptos):
    pdf = InvoicePDF()
    pdf.add_page()
    
    # Datos Emisor (Tú)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'EMISOR:', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Nombre: {datos_empresa['nombre']}", 0, 1)
    pdf.cell(0, 5, f"NIF: {datos_empresa['nif']}", 0, 1)
    pdf.ln(10)

    # Datos Receptor (Cliente)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'CLIENTE:', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Empresa: {datos_cliente['nombre']}", 0, 1)
    pdf.cell(0, 5, f"ID Cliente: {datos_cliente['id']}", 0, 1)
    pdf.ln(10)

    # Tabla de Conceptos
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(120, 10, 'Concepto', 1, 0, 'C', True)
    pdf.cell(70, 10, 'Total (inc. IVA)', 1, 1, 'C', True)
    
    for item in conceptos:
        pdf.cell(120, 10, item['nombre'], 1)
        pdf.cell(70, 10, f"{item['precio']} EUR", 1, 1, 'R')

    # Firma VeriFactu (Simulada para el viernes)
    pdf.ln(20)
    pdf.set_font('Courier', 'I', 8)
    pdf.multi_cell(0, 5, f"Huella Digital VeriFactu: {datos_empresa.get('hash', 'PENDIENTE_VALIDACION_AEAT')}")
    
    return pdf.output(dest='S').encode('latin-1') # Devuelve el chorro de datos del PDF