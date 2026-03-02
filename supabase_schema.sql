-- ============================================================
-- AB SOFTWARE EMPRESARIAL - Schema Supabase (PostgreSQL)
-- Ejecutar en el SQL Editor de Supabase
-- ============================================================

-- 1. USUARIOS (Autenticación propia)
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'empleado',  -- 'admin' | 'empleado' | 'gestor'
    nombre_completo TEXT,
    empresa_id TEXT NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. GASTOS (Libro de gastos contable)
CREATE TABLE IF NOT EXISTS gastos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    fecha DATE NOT NULL,
    empleado TEXT NOT NULL,
    proveedor TEXT,
    categoria TEXT,
    concepto TEXT,
    total_chf NUMERIC(12, 2) NOT NULL DEFAULT 0,
    moneda TEXT DEFAULT 'EUR',
    proyecto TEXT,
    notas TEXT,
    evidencia_url TEXT,  -- Ruta en Supabase Storage
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. PRESUPUESTOS / FACTURAS (Módulo Verifactu)
CREATE TABLE IF NOT EXISTS presupuestos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    cliente TEXT NOT NULL,
    nif_cliente TEXT,
    nif_empresa TEXT,
    titulo TEXT,
    total_neto NUMERIC(12, 2),
    impuestos NUMERIC(12, 2),
    total_final NUMERIC(12, 2) NOT NULL DEFAULT 0,
    iva_porcentaje NUMERIC(5, 2) DEFAULT 21.0,
    moneda TEXT DEFAULT 'EUR',
    estado TEXT DEFAULT 'Pendiente',  -- 'Pendiente' | 'Facturado' | 'Anulado'
    tipo_factura TEXT DEFAULT 'NORMAL',  -- 'NORMAL' | 'RECTIFICATIVA' | 'ANULACION'
    -- Verifactu
    num_factura TEXT UNIQUE,
    numero_secuencial INTEGER,
    fecha DATE,
    fecha_factura DATE,
    hash_factura TEXT,
    hash_anterior TEXT,
    bloqueado BOOLEAN DEFAULT FALSE,
    -- Extras
    items JSONB,
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_presupuestos_empresa ON presupuestos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_presupuestos_num ON presupuestos(num_factura);
CREATE INDEX IF NOT EXISTS idx_presupuestos_seq ON presupuestos(empresa_id, numero_secuencial);

-- 4. INVENTARIO
CREATE TABLE IF NOT EXISTS inventario (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    categoria TEXT,
    stock INTEGER DEFAULT 0,
    minimo INTEGER DEFAULT 1,
    ubicacion TEXT,
    responsable TEXT,
    estado TEXT DEFAULT 'Disponible',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. FLOTA (Vehículos)
CREATE TABLE IF NOT EXISTS flota (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    matricula TEXT,
    marca TEXT,
    modelo TEXT,
    tipo TEXT,
    km_actuales INTEGER DEFAULT 0,
    km_proximo_servicio INTEGER,
    conductor_asignado TEXT,
    estado TEXT DEFAULT 'Operativo',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. RRHH (Empleados)
CREATE TABLE IF NOT EXISTS empleados (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    nif TEXT,
    puesto TEXT,
    departamento TEXT,
    fecha_alta DATE,
    salario_bruto NUMERIC(10, 2),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. AUDITORÍA VERIFACTU (Obligatorio para cumplimiento fiscal)
CREATE TABLE IF NOT EXISTS auditoria (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT,
    accion TEXT NOT NULL,
    tabla TEXT,
    registro_id TEXT,
    cambios JSONB,
    fecha TIMESTAMPTZ DEFAULT NOW(),
    usuario TEXT
);

-- 8. ECO / SOSTENIBILIDAD
CREATE TABLE IF NOT EXISTS eco_registros (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id TEXT NOT NULL,
    fecha DATE,
    tipo TEXT,  -- 'combustible' | 'electricidad' | 'residuos'
    cantidad NUMERIC(10, 2),
    unidad TEXT,
    co2_kg NUMERIC(10, 2),
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) - Activar en producción
-- ============================================================
-- ALTER TABLE gastos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE presupuestos ENABLE ROW LEVEL SECURITY;
-- ... (configurar políticas según empresa_id)

-- ============================================================
-- USUARIO DEMO (SHA256 de "demo1234")
-- ============================================================
INSERT INTO usuarios (username, password_hash, rol, nombre_completo, empresa_id)
VALUES (
    'admin',
    '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92',  -- '123456'
    'admin',
    'Administrador Demo',
    'empresa_demo_01'
) ON CONFLICT (username) DO NOTHING;

-- Tablas clave Verifactu
ALTER TABLE public.presupuestos
    ADD COLUMN IF NOT EXISTS num_factura text,
    ADD COLUMN IF NOT EXISTS hash_factura text,
    ADD COLUMN IF NOT EXISTS numero_secuencial integer,
    ADD COLUMN IF NOT EXISTS tipo_factura text DEFAULT 'NORMAL',
    ADD COLUMN IF NOT EXISTS bloqueado boolean DEFAULT false;
CREATE OR REPLACE FUNCTION public.set_empresa_context(p_empresa_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_config('app.empresa_id', p_empresa_id::text, true);
END;
$$;

ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;

CREATE POLICY gastos_por_empresa
ON public.gastos
FOR ALL
USING (empresa_id::text = current_setting('app.empresa_id', true))
WITH CHECK (empresa_id::text = current_setting('app.empresa_id', true));

