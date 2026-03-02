# AB Software Empresarial

**SaaS de gestión empresarial con Verifactu** para pymes y autónomos en España/Galicia.

---

## 🚀 Puesta en Marcha (Producción)

### 1. Requisitos
```bash
pip install -r requirements.txt
```

### 2. Base de Datos (Supabase)
1. Crear proyecto en [supabase.com](https://supabase.com) (plan gratuito válido para empezar)
2. Ir a **SQL Editor** y ejecutar `supabase_schema.sql`
3. Activar **Storage** y crear bucket `tickets` (para adjuntos de gastos)

### 3. Configuración de Secretos
Copiar `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` y rellenar:
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIs..."
NIF_EMPRESA = "B12345678"
```

### 4. Ejecutar en local
```bash
streamlit run main.py
```
Usuario demo: `admin` / contraseña: `123456`

---

## ☁️ Despliegue en Streamlit Cloud
1. Subir código a GitHub (sin `secrets.toml`)
2. Ir a [share.streamlit.io](https://share.streamlit.io)
3. Conectar repositorio → **Settings → Secrets** → pegar contenido del secrets.toml

---

## 📁 Estructura del Proyecto
```
ab_software/
├── main.py                    # Punto de entrada + router
├── requirements.txt
├── supabase_schema.sql        # Ejecutar una sola vez en Supabase
├── .streamlit/
│   └── secrets.toml           # Credenciales (NO subir a Git)
├── services/
│   ├── auth_service.py        # Login / usuarios
│   ├── verifactu_service.py   # Hash SHA-256 + trazabilidad fiscal
│   ├── finance_service.py     # Gastos
│   ├── inventory_service.py   # Stock
│   ├── qr_helper.py           # Generación QR facturas
│   └── database.py            # Conexión Supabase singleton
├── views/
│   ├── dashboard_view.py      # KPIs + gráficos
│   ├── presupuestos_view.py   # Presupuestos + facturación Verifactu
│   ├── gastos_view.py         # Registro de gastos (OCR Azure)
│   ├── inventory_view.py      # Control de stock
│   ├── flota_view.py          # Gestión de vehículos
│   ├── rrhh_view.py           # RRHH básico
│   ├── eco_view.py            # Sostenibilidad
│   └── verify_public.py       # Página pública verificación QR
└── utils/
    └── azure_helper.py        # OCR Azure Form Recognizer
```

---

## ⚖️ Cumplimiento Verifactu (RDL 4/2023)
- ✅ Numeración secuencial consecutiva por empresa
- ✅ Hash SHA-256 encadenado (blockchain-style)
- ✅ Código QR en cada factura con URL de verificación pública
- ✅ Página de verificación pública sin login (`?num=FAC-...&hash=...`)
- ✅ Exportación de Libro de Registros en CSV (formato AEAT)
- ✅ Auditoría de integridad de cadena de hashes
- ✅ Anulación y rectificación de facturas sin borrado

---

## 🔧 Errores Corregidos (v1.1)
| Archivo | Error | Corrección |
|---------|-------|-----------|
| `main.py` | `from supabase_py import` (paquete obsoleto) | `from supabase import` |
| `verify_public.py` | `st.set_page_config()` duplicado | Eliminado (solo en main.py) |
| `verify_public.py` | `if not res.` (SyntaxError incompleto) | `if not res.data:` |
| `presupuestos_view.py` | `style.apply()` sin DataFrame | `.style.apply()` sobre df_display |
| `presupuestos_view.py` | `if res_libro:` (siempre True) | `if res_libro.data:` |
| `presupuestos_view.py` | `if not res_audit:` (siempre False) | `if not res_audit.data:` |
| `presupuestos_view.py` | `df_hist.get('tipo_factura')` (pandas no tiene `.get()`) | `.fillna('NORMAL')` |
| `verifactu_service.py` | Métodos `anular_factura()` y `crear_factura_rectificativa()` llamados pero no definidos | Implementados |
| `verify_public.py` | Creaba nueva conexión DB redundante | Recibe `db` como parámetro |

