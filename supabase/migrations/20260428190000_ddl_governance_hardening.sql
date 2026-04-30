BEGIN;

-- ============================================================================
-- DDL governance hardening
-- Objetivo: reducir capacidad de sabotaje con credenciales de backend comprometidas.
-- ============================================================================

-- Revoca operaciones destructivas sobre tablas fiscales inmutables.
REVOKE TRUNCATE ON TABLE public.facturas, public.auditoria FROM authenticated;
REVOKE TRUNCATE ON TABLE public.facturas, public.auditoria FROM service_role;

-- Evita creación/manipulación de triggers por roles de aplicación.
REVOKE TRIGGER ON TABLE public.facturas, public.auditoria FROM authenticated;
REVOKE TRIGGER ON TABLE public.facturas, public.auditoria FROM service_role;

-- Bloquea acceso al schema de extensiones desde roles de aplicación.
REVOKE ALL ON SCHEMA extensions FROM authenticated;
REVOKE ALL ON SCHEMA extensions FROM service_role;

COMMIT;
