locals {
  production_environment_id = railway_project.app.default_environment.id

  supabase_service_key_effective = trimspace(var.supabase_service_key) != "" ? var.supabase_service_key : var.supabase_key

  backend_common = [
    { name = "SUPABASE_URL", value = var.supabase_url },
    { name = "SUPABASE_KEY", value = var.supabase_key },
    { name = "SUPABASE_SERVICE_KEY", value = local.supabase_service_key_effective },
    { name = "JWT_SECRET_KEY", value = var.jwt_secret_key },
    { name = "SESSION_SECRET_KEY", value = var.session_secret_key },
    { name = "DATABASE_URL", value = var.database_url_production },
    { name = "REDIS_URL", value = var.redis_url_production },
    { name = "SECURITY_CONTACT_EMAIL", value = var.security_contact_email },
  ]

  backend_production_vars = concat(
    local.backend_common,
    [
      { name = "ENVIRONMENT", value = "production" },
      { name = "DEBUG", value = "False" },
      { name = "OFFICIAL_FRONTEND_ORIGIN", value = var.official_frontend_origin_production },
    ],
    trimspace(var.cors_allow_origins_extra_production) != "" ? [{ name = "CORS_ALLOW_ORIGINS", value = var.cors_allow_origins_extra_production }] : [],
    trimspace(var.maps_api_key) != "" ? [{ name = "Maps_API_KEY", value = var.maps_api_key }] : [],
  )

  backend_staging_vars = concat(
    [
      { name = "SUPABASE_URL", value = var.supabase_url },
      { name = "SUPABASE_KEY", value = var.supabase_key },
      { name = "SUPABASE_SERVICE_KEY", value = local.supabase_service_key_effective },
      { name = "JWT_SECRET_KEY", value = var.jwt_secret_key },
      { name = "SESSION_SECRET_KEY", value = var.session_secret_key },
      { name = "DATABASE_URL", value = var.database_url_staging },
      { name = "REDIS_URL", value = var.redis_url_staging },
      { name = "SECURITY_CONTACT_EMAIL", value = var.security_contact_email },
      { name = "ENVIRONMENT", value = "staging" },
      { name = "DEBUG", value = "True" },
      { name = "OFFICIAL_FRONTEND_ORIGIN", value = var.official_frontend_origin_staging },
    ],
    trimspace(var.cors_allow_origins_extra_staging) != "" ? [{ name = "CORS_ALLOW_ORIGINS", value = var.cors_allow_origins_extra_staging }] : [],
    trimspace(var.maps_api_key) != "" ? [{ name = "Maps_API_KEY", value = var.maps_api_key }] : [],
  )

  worker_production_vars = [
    { name = "SUPABASE_URL", value = var.supabase_url },
    { name = "SUPABASE_KEY", value = var.supabase_key },
    { name = "SUPABASE_SERVICE_KEY", value = local.supabase_service_key_effective },
    { name = "JWT_SECRET_KEY", value = var.jwt_secret_key },
    { name = "SESSION_SECRET_KEY", value = var.session_secret_key },
    { name = "DATABASE_URL", value = var.database_url_production },
    { name = "REDIS_URL", value = var.redis_url_production },
    { name = "ENVIRONMENT", value = "production" },
    # Railpack prioriza ``web`` del Procfile; el worker debe ejecutar ARQ explícitamente.
    { name = "RAILPACK_START_CMD", value = "sh scripts/start-worker.sh" },
  ]

  worker_staging_vars = [
    { name = "SUPABASE_URL", value = var.supabase_url },
    { name = "SUPABASE_KEY", value = var.supabase_key },
    { name = "SUPABASE_SERVICE_KEY", value = local.supabase_service_key_effective },
    { name = "JWT_SECRET_KEY", value = var.jwt_secret_key },
    { name = "SESSION_SECRET_KEY", value = var.session_secret_key },
    { name = "DATABASE_URL", value = var.database_url_staging },
    { name = "REDIS_URL", value = var.redis_url_staging },
    { name = "ENVIRONMENT", value = "staging" },
    { name = "DEBUG", value = "True" },
    { name = "RAILPACK_START_CMD", value = "sh scripts/start-worker.sh" },
  ]
}

resource "railway_project" "app" {
  name        = var.project_name
  description = "AB Logistics OS — definición Terraform (IaC / Gap 119)."
  private     = true

  workspace_id = trimspace(var.railway_workspace_id) != "" ? var.railway_workspace_id : null

  default_environment = {
    name = "production"
  }
}

resource "railway_environment" "staging" {
  name       = "staging"
  project_id = railway_project.app.id
}

resource "railway_service" "backend_production" {
  name               = "ab-software-erp"
  project_id         = railway_project.app.id
  source_repo        = var.github_repo
  source_repo_branch = var.git_branch_production
  root_directory     = "backend"
  config_path        = "/backend/railway.json"
}

resource "railway_service" "worker_production" {
  name               = "ab-software-worker"
  project_id         = railway_project.app.id
  source_repo        = var.github_repo
  source_repo_branch = var.git_branch_production
  root_directory     = "backend"
  config_path        = "/infra/railway/worker.railway.json"
}

resource "railway_service" "backend_staging" {
  name               = "backend-staging"
  project_id         = railway_project.app.id
  source_repo        = var.github_repo
  source_repo_branch = var.git_branch_staging
  root_directory     = "backend"
  config_path        = "/backend/railway.json"
}

resource "railway_service" "worker_staging" {
  name               = "worker-staging"
  project_id         = railway_project.app.id
  source_repo        = var.github_repo
  source_repo_branch = var.git_branch_staging
  root_directory     = "backend"
  config_path        = "/infra/railway/worker.railway.json"
}

resource "railway_variable_collection" "backend_production" {
  environment_id = local.production_environment_id
  service_id     = railway_service.backend_production.id
  variables      = local.backend_production_vars
}

resource "railway_variable_collection" "worker_production" {
  environment_id = local.production_environment_id
  service_id     = railway_service.worker_production.id
  variables      = local.worker_production_vars
}

# Staging API/worker usan ramas y URLs de staging, pero el recurso railway_service
# no fija environment_id: Railway asocia el servicio al entorno por defecto del
# proyecto (p. ej. "production"). Si las variables solo existían en railway_environment.staging,
# el runtime veía SUPABASE_URL vacío → CRASHED / healthcheck failure.
resource "railway_variable_collection" "backend_staging" {
  environment_id = local.production_environment_id
  service_id     = railway_service.backend_staging.id
  variables      = local.backend_staging_vars
}

resource "railway_variable_collection" "worker_staging" {
  environment_id = local.production_environment_id
  service_id     = railway_service.worker_staging.id
  variables      = local.worker_staging_vars
}
