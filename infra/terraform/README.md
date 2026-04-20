# Terraform — Railway (AB Logistics OS)

Provider: [`terraform-community-providers/railway`](https://registry.terraform.io/providers/terraform-community-providers/railway/latest) (no oficial; suficiente para proyecto, entornos, servicios y variables).

## Qué crea este módulo

- Proyecto Railway con entorno por defecto `production` y un entorno adicional `staging`.
- Servicios de cómputo:
  - **production**: `backend` + `worker` (rama `git_branch_production`).
  - **staging**: `backend-staging` + `worker-staging` (rama `git_branch_staging`).
- Colecciones de variables por servicio y entorno (Supabase, JWT, sesión, Postgres, Redis, `SECURITY_CONTACT_EMAIL`, `ENVIRONMENT`, orígenes CORS).

## Qué no crea (limitación del provider / API)

- Los **plugins** de **PostgreSQL** y **Redis** deben añadirse en Railway (canvas: *New → Database*) o importarse después. Las URLs suelen enlazarse con **referencias de variables** (`Service.VARIABLE`) documentadas en `docs/INFRASTRUCTURE.md`.
- **Copias de seguridad automáticas** de Postgres: se configuran en el servicio de base de datos en Railway (plan y opciones de backup), no en este repositorio.

## Uso local

```bash
cd infra/terraform
export RAILWAY_TOKEN="..."   # token de cuenta con permisos en el workspace
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars con valores reales

terraform init
terraform plan
terraform apply
```

## Estado remoto (recomendado en empresa)

Por defecto el estado es **local**. Para equipo o CI compartido, configure un backend S3, GCS o Terraform Cloud y documente el bucket en su runbook interno.

## GitHub Actions

El workflow raíz `.github/workflows/deploy.yml` aplica este directorio cuando cambian rutas bajo `infra/terraform/**` o `infra/railway/**` en push a `main`. Requiere el secret `RAILWAY_TOKEN` y variables `TF_VAR_*` definidas en el repositorio (ver `docs/INFRASTRUCTURE.md`).
