# Infraestructura reproducible — Railway (AB Logistics OS)

Este documento está orientado a un **adquirente** o equipo de plataforma que debe levantar el ecosistema en una **cuenta nueva de Railway** con el menor número de pasos manuales posible, alineado con el cierre del **Gap 119** (IaC / pipeline formal).

## 1. Arquitectura lógica

| Capa | Tecnología | Rol |
|------|------------|-----|
| API HTTP | **FastAPI** (`backend/`) | Servicio `backend` / `backend-staging` en Railway. |
| Colas asíncronas | **ARQ** + **Redis** | Servicio `worker` / `worker-staging`; requiere `REDIS_URL`. |
| Rate limiting / colas | **Redis** + SlowAPI / `limits` | Misma `REDIS_URL` que ARQ (instancia compartida recomendada en Railway). |
| Datos transaccionales | **PostgreSQL** (`DATABASE_URL`) | SQLAlchemy; en producción la app **exige** `DATABASE_URL` explícita. |
| Auth / storage / RLS | **Supabase** | `SUPABASE_URL`, claves y JWKS; Postgres puede ser el de Supabase o uno dedicado en Railway según diseño. |

Referencia de variables de aplicación: `docs/DEPLOYMENT.md`, `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md`, `docs/operations/REDIS_001_HA_BILLING_QUEUE.md` y `backend/app/core/config.py`. El backend Terraform incluye `SECURITY_CONTACT_EMAIL` (divulgación RFC 9116; por defecto `security@ablogistics-os.com` — crear el buzón y MX en el dominio antes de go-live).

## 2. Qué hay en el repositorio

| Ruta | Propósito |
|------|-----------|
| `infra/terraform/` | **Terraform** con el provider comunitario [`railway`](https://registry.terraform.io/providers/terraform-community-providers/railway/latest): proyecto, entorno `staging`, servicios de cómputo y variables por entorno. |
| `backend/railway.json` | Config as Code del **API** (Nixpacks, `uvicorn`, healthcheck `GET /live`). |
| `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md` | Manual operativo OPS-001 de topología VPS/Railway/Vercel: servicios, dominios, variables, despliegue, backups y responsables. |
| `docs/operations/REDIS_001_HA_BILLING_QUEUE.md` | Runbook REDIS-001: HA de Redis para cola de facturación, retry/backoff del worker y observabilidad de fallos. |
| `docs/operations/DISASTER_RECOVERY.md` | **DRP** (RPO/RTO, escenarios, enlaces a runbooks). |
| `infra/railway/worker.railway.json` | Config as Code del **worker ARQ** (`arq app.worker.WorkerSettings`). |
| `.github/workflows/deploy.yml` | CI/CD existente más job **Railway IaC**: plan o apply de Terraform según configuración (ver §6). |

**Nota:** El provider de Terraform para Railway es **comunitario** (no mantenido por Railway, Inc.). Es adecuado para servicios y variables; los **plugins** de Postgres/Redis del marketplace siguen creándose en el lienzo de Railway (o importándose) y se enlazan por **referencias de variables** (§4).

## 3. Entornos Staging / Production

Terraform define:

- Entorno **production** (el predeterminado del proyecto Railway).
- Entorno **staging** (`railway_environment`).
- **Cuatro** servicios de despliegue:
  - **Production:** `backend` + `worker` (rama `git_branch_production`, por defecto `main`).
  - **Staging:** `backend-staging` + `worker-staging` (rama `git_branch_staging`, por defecto `staging`).

Cada par tiene su propia **colección de variables** (`railway_variable_collection`) para que CORS, `DATABASE_URL` y secretos puedan diferir entre entornos sin mezclar estado.

Mantenga una rama `staging` en Git que despliegue solo el stack de staging; `main` sigue siendo la línea principal de producción.

## 4. PostgreSQL y Redis en Railway

El provider **no** provisiona hoy los contenedores de plantilla “PostgreSQL” / “Redis” del marketplace. Flujo recomendado:

1. En el proyecto Railway, **New → Database → PostgreSQL** y **New → Database → Redis**.
2. Asigne nombres **estables** en el canvas (por defecto suelen ser `Postgres` y `Redis`).
3. En las variables de `backend` y `worker`, use **referencias** en lugar de copiar URLs (evita deriva y secretos duplicados). En el panel de variables de Railway, al insertar una referencia, la UI ofrece el formato `Service.VARIABLE`. Ejemplos habituales:
   - Conexión a Postgres: variable de servicio tipo `DATABASE_URL` del plugin Postgres.
   - Redis: `REDIS_URL` o `REDIS_PUBLIC_URL` según exponga la plantilla (compruebe el panel del servicio Redis).

Para **Terraform**, puede pasar esas referencias como valores de `database_url_*` y `redis_url_*`. En un archivo `.tfvars`, el carácter `$` debe escaparse para Terraform:

```hcl
database_url_production = "$${{ Postgres.DATABASE_URL }}"
redis_url_production    = "$${{ Redis.REDIS_URL }}"
```

(Eso guarda en Railway la cadena literal `${{ Postgres.DATABASE_URL }}`, que la plataforma resuelve en tiempo de despliegue.)

### Copias de seguridad (Postgres)

Las **backups automáticas** dependen del **plan de Railway** y de la configuración del servicio Postgres (panel del plugin → backups / retención). No están modeladas en el Terraform de este repositorio; el cumplimiento de RPO/RTO debe verificarse en contrato con Railway y en el runbook de operaciones.

## 5. Despliegue desde cero (cuenta nueva)

### 5.1 Prerrequisitos

- Cuenta **Railway** y token de API: [Account tokens](https://railway.com/account/tokens).
- Repositorio Git (GitHub) con el código; el token debe poder conectar el repo a Railway si usa `source_repo` en Terraform.
- Proyecto **Supabase** (o equivalente) y claves.
- Secreto de aplicación: `JWT_SECRET_KEY`, `SESSION_SECRET_KEY`, y opcionalmente `Maps_API_KEY`.

### 5.2 Plugins de datos

1. Cree el proyecto (o deje que Terraform cree el proyecto en §5.3).
2. Añada **Postgres** y **Redis** al proyecto.
3. Confirme los nombres de servicio usados en las referencias `${{ ... }}`.

### 5.3 Terraform (primera aplicación)

```bash
cd infra/terraform
export RAILWAY_TOKEN="..."
cp terraform.tfvars.example terraform.tfvars
# Edite terraform.tfvars: project_name, github_repo, orígenes CORS, secretos y URLs/referencias.

terraform init
terraform plan
terraform apply
```

Revise los IDs en `terraform output` y valide en el dashboard de Railway que los cuatro servicios de cómputo existen y que las variables aparecen en el lienzo (el entorno por defecto del proyecto suele llamarse **production**).

**Healthcheck failure / worker CRASHED con `Missing required env var: SUPABASE_URL`:** el contenedor arranca Uvicorn pero falla al importar la app si `SUPABASE_URL` / `SUPABASE_KEY` no están en el **mismo entorno Railway** donde corre el servicio. El provider `railway_service` no fija `environment_id`; los servicios suelen quedar en el entorno por defecto del proyecto. Las colecciones de Terraform para `backend-staging` y `worker-staging` deben usar ese entorno (no solo el recurso `railway_environment.staging` aislado). Compruebe también que los secretos GitHub `TF_VAR_SUPABASE_*` no estén vacíos antes de `terraform apply`.

### 5.4 Config as Code en el servicio

En cada servicio de aplicación, en **Settings → Build → Config file**, use rutas **absolutas** desde la raíz del repo (Railway no hereda la ruta relativa del root directory):

- API: `/backend/railway.json`
- Worker: `/infra/railway/worker.railway.json`

**Root directory** del servicio: `backend` (mismo para API y worker: mismo código, distinto `railway.json`).

### 5.5 Verificación

- `GET /health` en la URL pública del `backend`.
- Readiness: `GET /ready` (si está expuesto en su versión de API).
- Encolar un job ARQ y comprobar logs del `worker`.

## 6. GitOps — GitHub Actions

El job **Railway IaC (Terraform)** en `.github/workflows/deploy.yml`:

- Se ejecuta en **push** a `main` o `master` **solo** si cambian archivos bajo `infra/terraform/**` o `infra/railway/**`.
- Requiere `RAILWAY_TOKEN` en **Secrets**.
- Requiere variables de Terraform vía prefijo **`TF_VAR_`** (convención estándar de Terraform). Defina al menos:

| Variable Terraform | Secret / Variable GitHub (prefijo `TF_VAR_` en el nombre del *secret* o *variable*) |
|--------------------|-----------------------------------|
| `project_name` | Variable `TF_VAR_project_name` |
| `github_repo` | Variable `TF_VAR_github_repo` |
| `official_frontend_origin_production` | Variable `TF_VAR_official_frontend_origin_production` |
| `official_frontend_origin_staging` | Variable `TF_VAR_official_frontend_origin_staging` |
| `supabase_url`, `supabase_key`, `supabase_service_key` | Secrets `TF_VAR_SUPABASE_URL`, `TF_VAR_SUPABASE_KEY`, `TF_VAR_SUPABASE_SERVICE_KEY` |
| `jwt_secret_key`, `session_secret_key` | Secrets `TF_VAR_JWT_SECRET_KEY`, `TF_VAR_SESSION_SECRET_KEY` |
| `database_url_production`, `database_url_staging`, `redis_url_production`, `redis_url_staging` | Secrets `TF_VAR_DATABASE_URL_PRODUCTION`, etc. (pueden contener referencias Railway; en `.tfvars` escapar `$` como en §4) |
| `maps_api_key` | Secret `TF_VAR_MAPS_API_KEY` (opcional; puede estar vacío) |

Otras variables (`git_branch_*`, `railway_workspace_id`, `cors_allow_origins_extra_*`) tienen **default** en Terraform; si hace falta sobreescribirlas en CI, añada variables de repositorio con el nombre exacto `TF_VAR_<nombre>` (minúsculas con guiones bajos tras el prefijo, p. ej. `TF_VAR_git_branch_staging`).

### Estado de Terraform (obligatorio para apply en CI)

Sin **backend remoto**, cada ejecución en GitHub Actions tendría **estado efímero** y un `apply` recrearía o duplicaría recursos.

Por tanto:

1. Configure un backend remoto (recomendado: **S3 + DynamoDB** o **Terraform Cloud**). Véase `infra/terraform/backend.auto.tf.example`.
2. En el repositorio, cree el secret multilínea **`TF_BACKEND_HCL`** con el bloque `terraform { backend "s3" { ... } }` (o equivalente).
3. Active la variable de repositorio **`RAILWAY_TERRAFORM_APPLY_ENABLED`** con el valor `true` **solo** cuando el backend y los secretos `TF_VAR_*` estén listos.

Si `RAILWAY_TERRAFORM_APPLY_ENABLED` no es `true`, el job ejecuta **`terraform plan`** (sin apply) para visibilidad y no modifica Railway.

## 7. Relación con Supabase

Muchos despliegues usan **Postgres administrado por Supabase** y solo Railway para la API y workers. En ese caso:

- `DATABASE_URL` suele ser la cadena de conexión directa (o pooler) de Supabase, no el plugin Postgres de Railway.
- Siga añadiendo **Redis** en Railway para rate limiting distribuido y ARQ.

Ajuste las variables en `terraform.tfvars` en consecuencia; el módulo no impone un u otro proveedor de Postgres.

## 8. Resumen de riesgos y transparencia (due diligence)

| Riesgo | Mitigación |
|--------|------------|
| Provider Railway no oficial | Fijar versión en `versions.tf`; revisar changelog antes de upgrades. |
| Estado local perdido en CI | Backend remoto + job condicionado (`RAILWAY_TERRAFORM_APPLY_ENABLED`). |
| Backups Postgres | Configuración explícita en el plugin y plan comercial Railway. |
| Ramas distintas por entorno | Cubierto con `backend-staging` / `worker-staging` apuntando a `git_branch_staging`. |

Para soporte interno adicional, consulte `infra/terraform/README.md` y el job de workflow enlazado anteriormente.

## 9. Contratos de plataforma (API, secretos, cola, portabilidad)

Para integradores, app móvil y reducción de **vendor lock-in** sin romper compatibilidad, véase
`docs/PLATFORM_CONTRACTS.md` (rutas `/api/v1`, Postgres, ARQ/Redis, webhooks).
