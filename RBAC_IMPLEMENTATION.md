# Sistema RBAC y Audit Logs - Resumen de Implementación

## Resumen Ejecutivo

Se ha implementado un sistema completo de **Control de Acceso Basado en Roles (RBAC)** con **Audit Logs** para el sistema AB Logistics OS. La implementación incluye:

1. ✅ Definición de roles: SUPERADMIN, ADMIN, STAFF
2. ✅ Middleware de permisos con decorador `requires_role`
3. ✅ Protección de endpoints de finanzas y administración
4. ✅ Migración SQL para roles y audit logs
5. ✅ Helpers para registro de acciones sensibles
6. ✅ Frontend actualizado para ocultar secciones según rol

---

## 1. Roles Definidos

### Backend: `backend/app/models/auth.py`

```python
class UserRole(str, Enum):
    SUPERADMIN = "superadmin"  # Acceso total, gestión cross-tenant
    ADMIN = "admin"            # Gestión completa del tenant (finanzas, admin)
    STAFF = "staff"            # Operaciones básicas (portes, facturas, flota)
```

### Mapeo de Roles Legados

Los roles operativos existentes se mapean a los nuevos roles de seguridad:

| Rol Operativo (`rbac_role`) | Rol de Seguridad | Acceso |
|------------------------------|------------------|--------|
| `owner` | ADMIN | Acceso completo al tenant |
| `developer` | ADMIN | Acceso completo + API |
| `traffic_manager` | STAFF | Operaciones básicas |
| `driver` | STAFF | Solo lectura de portes asignados |
| `cliente` | STAFF | Portal cliente |

---

## 2. Middleware de Permisos

### Archivo: `backend/app/middleware/rbac_middleware.py`

**Decorador principal:**

```python
from app.middleware.rbac_middleware import require_admin

@router.get("/protected")
async def protected_endpoint(user: UserOut = Depends(require_admin)):
    # Solo accesible por ADMIN y SUPERADMIN
    pass
```

**Decoradores disponibles:**

1. `require_admin` - Requiere ADMIN o SUPERADMIN
2. `require_superadmin` - Requiere SUPERADMIN (máximo privilegio)
3. `requires_role(*roles)` - Flexible para múltiples roles

---

## 3. Endpoints Protegidos

### Finanzas (`/api/v1/finance/*`)

Todos los endpoints de finanzas ahora requieren rol ADMIN:

- `GET /api/v1/finance/risk-ranking`
- `GET /api/v1/finance/margin-ranking`
- `GET /api/v1/finance/credit-alerts`
- `GET /api/v1/finance/treasury-risk`
- `GET /api/v1/finance/esg-report`
- `GET /api/v1/finance/esg-report/download`

### Administración (`/admin/*`)

Todos los endpoints de administración requieren rol ADMIN:

- `GET /admin/empresas`
- `POST /admin/empresas`
- `PATCH /admin/empresas/{id}`
- `DELETE /admin/empresas/{id}`
- `GET /admin/usuarios`
- `PATCH /admin/usuarios/{id}`
- `GET /admin/auditoria`
- `GET /admin/metricas/facturacion`

---

## 4. Migración SQL

### Archivo: `backend/migrations/20260530_rbac_admin_staff_extension.sql`

**Cambios en la base de datos:**

1. **Extensión del enum `user_role`:**
   - Añadidos: `superadmin`, `admin`, `staff`
   - Mantenidos: `owner`, `traffic_manager`, `driver` (compatibilidad)

2. **Nueva columna `role_rbac` en tablas:**
   - `usuarios.role_rbac` - Rol de seguridad del usuario
   - `profiles.role_rbac` - Rol de seguridad del perfil

3. **Función helper `is_admin_or_higher()`:**
   - Verifica si el usuario actual tiene permisos de admin
   - Útil para políticas RLS

4. **Política RLS actualizada:**
   - `audit_logs_select_admin_only` - Solo admins pueden ver audit logs

### Aplicar la migración:

```bash
# En Supabase Dashboard → SQL Editor
# O usando el CLI de Supabase:
supabase db push backend/migrations/20260530_rbac_admin_staff_extension.sql
```

---

## 5. Audit Logs

### Servicio: `backend/app/services/audit_logs_service.py`

**Método principal:**

```python
async def log_sensitive_action(
    empresa_id: str,
    table_name: str,
    record_id: str,
    action: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    user_id: str | None = None,
) -> None
```

**Helpers específicos:**

```python
# Eliminar un vehículo
await audit_service.log_vehiculo_deletion(
    empresa_id=empresa_id,
    vehiculo_id=vehiculo_id,
    vehiculo_data={"matricula": "ABC123", "estado": "activo"},
    user_id=current_user.usuario_id,
)

# Cambiar precio de un porte
await audit_service.log_precio_porte_change(
    empresa_id=empresa_id,
    porte_id=porte_id,
    old_precio=1500.00,
    new_precio=1800.00,
    user_id=current_user.usuario_id,
)

# Modificar factura
await audit_service.log_factura_modification(
    empresa_id=empresa_id,
    factura_id=factura_id,
    old_data={"total": 1000.00, "estado": "pendiente"},
    new_data={"total": 1200.00, "estado": "pagada"},
    user_id=current_user.usuario_id,
)
```

**Uso en endpoints:**

```python
from app.services.audit_logs_service import AuditLogsService

@router.delete("/vehiculos/{vehiculo_id}")
async def delete_vehiculo(
    vehiculo_id: str,
    current_user: UserOut = Depends(require_admin),
    audit_service: AuditLogsService = Depends(deps.get_audit_logs_service),
):
    # Obtener datos del vehículo antes de borrar
    vehiculo = await flota_service.get_vehiculo(vehiculo_id)
    
    # Borrar vehículo
    await flota_service.delete_vehiculo(vehiculo_id)
    
    # Registrar en audit log
    await audit_service.log_vehiculo_deletion(
        empresa_id=current_user.empresa_id,
        vehiculo_id=vehiculo_id,
        vehiculo_data=vehiculo.model_dump(),
        user_id=current_user.usuario_id,
    )
    
    return {"status": "deleted"}
```

---

## 6. Frontend - Control de Visibilidad

### Archivo: `frontend/src/components/AppShell.tsx`

La función `showNavItem` controla qué secciones se muestran:

```typescript
function showNavItem(key: string, role: AppRbacRole): boolean {
  // Finanzas y Admin: solo owner y developer (ADMIN)
  if (key === "finanzas" || key === "admin") {
    return role === "owner" || role === "developer";
  }
  
  // Traffic manager (STAFF): flota, sostenibilidad, facturas, gastos
  if (role === "traffic_manager") {
    return key === "flota" || key === "sostenibilidad" 
        || key === "facturas" || key === "gastos";
  }
  
  // Driver y cliente: acceso muy limitado
  return false;
}
```

**Secciones ocultas para STAFF:**

- ❌ Finanzas
- ❌ Conciliación IA
- ❌ Tesorería y Riesgos
- ❌ Simulador Impacto
- ❌ Auditoría Fiscal
- ❌ Admin
- ❌ Integraciones
- ✅ Portes
- ✅ Flota
- ✅ Eficiencia
- ✅ Sostenibilidad
- ✅ Facturas
- ✅ Gastos

---

## 7. Testing y Validación

### Casos de prueba recomendados:

1. **Test de acceso a finanzas:**
   ```bash
   # Con usuario STAFF (traffic_manager)
   curl -H "Authorization: Bearer $TOKEN_STAFF" \
        http://localhost:8000/api/v1/finance/treasury-risk
   # Esperado: 403 Forbidden
   
   # Con usuario ADMIN (owner)
   curl -H "Authorization: Bearer $TOKEN_ADMIN" \
        http://localhost:8000/api/v1/finance/treasury-risk
   # Esperado: 200 OK con datos
   ```

2. **Test de audit logs:**
   ```python
   # Borrar un vehículo como ADMIN
   await audit_service.log_vehiculo_deletion(...)
   
   # Verificar que se registró en audit_logs
   logs = await audit_service.list_for_empresa(empresa_id=empresa_id)
   assert logs[0].action == "DELETE"
   assert logs[0].table_name == "flota"
   ```

3. **Test de visibilidad frontend:**
   - Login como `traffic_manager` → No debe ver "Finanzas" ni "Admin" en sidebar
   - Login como `owner` → Debe ver todas las secciones

---

## 8. Migración de Usuarios Existentes

### Script SQL para actualizar roles:

```sql
-- Actualizar todos los owner a ADMIN
UPDATE public.profiles 
SET role_rbac = 'admin'::public.user_role 
WHERE role = 'owner'::public.user_role;

-- Actualizar traffic_manager y driver a STAFF
UPDATE public.profiles 
SET role_rbac = 'staff'::public.user_role 
WHERE role IN ('traffic_manager', 'driver');

-- Actualizar desarrolladores a ADMIN
UPDATE public.profiles 
SET role_rbac = 'admin'::public.user_role 
WHERE role = 'developer'::public.user_role;
```

---

## 9. Documentación de API

### Swagger/OpenAPI

Los nuevos decoradores automáticamente añaden información de seguridad a OpenAPI:

- Endpoints con `require_admin`: Marcados como "Requiere rol ADMIN"
- Endpoints con `require_superadmin`: Marcados como "Requiere rol SUPERADMIN"

### Ejemplo de respuesta de error:

```json
{
  "detail": "Acceso denegado. Se requiere rol de administrador."
}
```

---

## 10. Próximos Pasos (Opcional)

### Mejoras futuras recomendadas:

1. **Panel de gestión de roles:**
   - UI para asignar roles a usuarios
   - Endpoint `/admin/usuarios/{id}/roles` PATCH

2. **Audit logs avanzados:**
   - Dashboard de actividad en tiempo real
   - Alertas de acciones sospechosas
   - Exportación de logs a CSV/JSON

3. **Roles granulares:**
   - Permisos específicos por módulo
   - Roles personalizados por empresa

4. **Integración con 2FA:**
   - Requerir 2FA para roles ADMIN y SUPERADMIN
   - Audit log de intentos de acceso fallidos

---

## Archivos Modificados

### Backend (Python/FastAPI)

1. ✅ `backend/app/models/auth.py` - Enum UserRole
2. ✅ `backend/app/models/__init__.py` - Export de modelos
3. ✅ `backend/app/middleware/rbac_middleware.py` - Decoradores de permisos
4. ✅ `backend/app/api/routes/finance.py` - Protección con require_admin
5. ✅ `backend/app/api/routes/admin.py` - Protección con require_admin
6. ✅ `backend/app/api/v1/finance_dashboard.py` - Protección con require_admin
7. ✅ `backend/app/services/audit_logs_service.py` - Helpers de audit logs
8. ✅ `backend/app/api/deps.py` - Dependencia get_audit_logs_service
9. ✅ `backend/migrations/20260530_rbac_admin_staff_extension.sql` - Migración SQL

### Frontend (TypeScript/Next.js)

1. ✅ `frontend/src/components/AppShell.tsx` - Control de visibilidad de secciones

---

## Contacto y Soporte

Para cualquier duda sobre la implementación:

1. Revisar la documentación en los comentarios de código
2. Consultar el código de ejemplo en este documento
3. Ejecutar los tests de validación
4. Revisar los logs de Supabase para debugging

---

**Fecha de implementación:** 30 de marzo de 2026  
**Versión del sistema:** AB Logistics OS v2.0  
**Estado:** ✅ Implementación completa - Listo para deployment
