-- =============================================================================
-- Extensión del sistema RBAC: añadir roles SUPERADMIN, ADMIN y STAFF
-- Migración segura que mantiene compatibilidad con roles existentes
-- =============================================================================

-- 1. Extender el tipo user_role con los nuevos valores
-- Se mantienen los valores existentes: owner, traffic_manager, driver
-- Se añaden: superadmin, admin, staff
DO $$ BEGIN
  -- Primero verificamos si el tipo existe
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    CREATE TYPE public.user_role AS ENUM ('owner', 'traffic_manager', 'driver');
  END IF;
  
  -- Añadir nuevos valores al enum si no existen
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'superadmin';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'admin';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
  
  BEGIN
    ALTER TYPE public.user_role ADD VALUE IF NOT EXISTS 'staff';
  EXCEPTION
    WHEN duplicate_object THEN NULL;
  END;
END $$;

-- 2. Actualizar comentario del tipo para reflejar la nueva jerarquía
COMMENT ON TYPE public.user_role IS 
  'Roles RBAC del sistema. Jerarquía: superadmin (gestión cross-tenant), admin (gestión completa del tenant), staff (operaciones básicas), owner/traffic_manager/driver (roles operativos legados)';

-- 3. Añadir columna de auditoría en usuarios si no existe
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'usuarios'
  ) THEN
    -- Añadir columna role_rbac si no existe (para distinguir del rol operativo)
    ALTER TABLE public.usuarios
      ADD COLUMN IF NOT EXISTS role_rbac public.user_role NOT NULL DEFAULT 'staff'::public.user_role;
    
    COMMENT ON COLUMN public.usuarios.role_rbac IS
      'Rol RBAC de seguridad (superadmin/admin/staff). Controla acceso a secciones sensibles: finanzas, administración.';
  END IF;
END $$;

-- 4. Actualizar profiles con el nuevo sistema de roles
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) THEN
    -- Añadir columna role_rbac también en profiles para consistencia
    ALTER TABLE public.profiles
      ADD COLUMN IF NOT EXISTS role_rbac public.user_role NOT NULL DEFAULT 'staff'::public.user_role;
    
    COMMENT ON COLUMN public.profiles.role_rbac IS
      'Rol RBAC de seguridad (superadmin/admin/staff). Independiente del rol operativo (role).';
    
    -- Migración de datos: owner legado → admin, resto → staff
    -- Esta es una migración conservadora que puede ajustarse según necesidades
    UPDATE public.profiles 
    SET role_rbac = 'admin'::public.user_role 
    WHERE role = 'owner'::public.user_role 
      AND role_rbac = 'staff'::public.user_role;
  END IF;
END $$;

-- 5. Actualizar función set_rbac_session para soportar los nuevos roles
CREATE OR REPLACE FUNCTION public.set_rbac_session(
  p_rbac_role text,
  p_assigned_vehiculo_id uuid DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  r text;
BEGIN
  r := lower(trim(both from coalesce(p_rbac_role, 'staff')));
  
  -- Validar que el rol sea uno de los permitidos
  IF r NOT IN ('superadmin', 'admin', 'staff', 'owner', 'traffic_manager', 'driver', 'cliente', 'developer') THEN
    r := 'staff';
  END IF;
  
  PERFORM set_config('app.rbac_role', r, true);
  
  IF p_assigned_vehiculo_id IS NULL THEN
    PERFORM set_config('app.assigned_vehiculo_id', '', true);
  ELSE
    PERFORM set_config('app.assigned_vehiculo_id', p_assigned_vehiculo_id::text, true);
  END IF;
END;
$$;

COMMENT ON FUNCTION public.set_rbac_session(text, uuid) IS
  'Fija app.rbac_role y app.assigned_vehiculo_id para políticas RLS. Soporta roles: superadmin, admin, staff, owner, traffic_manager, driver, cliente, developer.';

-- 6. Crear helper function para verificar si un usuario tiene permisos de admin
CREATE OR REPLACE FUNCTION public.is_admin_or_higher()
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
DECLARE
  current_role text;
BEGIN
  current_role := public.app_rbac_role();
  RETURN current_role IN ('superadmin', 'admin', 'owner', 'developer');
END;
$$;

COMMENT ON FUNCTION public.is_admin_or_higher() IS
  'Retorna true si el rol actual tiene permisos de administrador (superadmin, admin, owner, developer)';

-- 7. Actualizar políticas RLS para soportar verificación de admin
-- Ejemplo: política más estricta para audit_logs
DROP POLICY IF EXISTS audit_logs_select_admin_only ON public.audit_logs;
CREATE POLICY audit_logs_select_admin_only ON public.audit_logs
  FOR SELECT
  USING (
    public.app_current_empresa_id()::text IS NOT NULL
    AND empresa_id::text = public.app_current_empresa_id()::text
    AND public.is_admin_or_higher()
  );

-- 8. Crear índices para optimizar consultas por rol
CREATE INDEX IF NOT EXISTS idx_usuarios_role_rbac 
  ON public.usuarios (role_rbac);

CREATE INDEX IF NOT EXISTS idx_profiles_role_rbac 
  ON public.profiles (role_rbac);

-- 9. Trigger para audit_logs que capture el rol del usuario
CREATE OR REPLACE FUNCTION public.audit_log_with_role()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_empresa uuid;
  v_old jsonb;
  v_new jsonb;
  v_record_id text;
  v_action public.audit_action;
  v_current_role text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    v_action := 'INSERT';
    v_old := NULL;
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'UPDATE' THEN
    v_action := 'UPDATE';
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    v_empresa := NEW.empresa_id;
  ELSIF TG_OP = 'DELETE' THEN
    v_action := 'DELETE';
    v_old := to_jsonb(OLD);
    v_new := NULL;
    v_empresa := OLD.empresa_id;
  ELSE
    RETURN COALESCE(NEW, OLD);
  END IF;

  v_record_id := coalesce(v_new->>'id', v_old->>'id');
  IF v_record_id IS NULL OR length(trim(v_record_id)) = 0 THEN
    v_record_id := gen_random_uuid()::text;
  END IF;

  -- Capturar rol actual para auditoría
  v_current_role := public.app_rbac_role();

  -- Añadir el rol al nuevo registro de auditoría
  v_new := jsonb_set(
    coalesce(v_new, '{}'::jsonb), 
    '{_audit_role}', 
    to_jsonb(v_current_role)
  );

  INSERT INTO public.audit_logs (
    empresa_id,
    table_name,
    record_id,
    action,
    old_data,
    new_data,
    changed_by
  ) VALUES (
    v_empresa,
    TG_TABLE_NAME::varchar(128),
    v_record_id,
    v_action,
    v_old,
    v_new,
    auth.uid()
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;

COMMENT ON FUNCTION public.audit_log_with_role() IS
  'Trigger de auditoría que captura el rol del usuario en el campo _audit_role de new_data';

-- 10. Información de la migración
DO $$
BEGIN
  RAISE NOTICE 'Migración RBAC completada:';
  RAISE NOTICE '- Enum user_role extendido con: superadmin, admin, staff';
  RAISE NOTICE '- Columna role_rbac añadida a usuarios y profiles';
  RAISE NOTICE '- Función is_admin_or_higher() creada';
  RAISE NOTICE '- Políticas RLS actualizadas para audit_logs';
  RAISE NOTICE '- Índices creados para optimizar consultas por rol';
END $$;
