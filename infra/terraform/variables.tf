variable "railway_token" {
  type        = string
  sensitive   = true
  default     = ""
  description = "API token (https://railway.com/account/tokens). In CI use RAILWAY_TOKEN; leave empty locally if the env var is set."
}

variable "railway_workspace_id" {
  type        = string
  default     = ""
  description = "Obligatorio si el token tiene acceso a varios workspaces de Railway."
}

variable "project_name" {
  type        = string
  description = "Nombre del proyecto en Railway (p. ej. ab-logistics-os-prod)."
}

variable "github_repo" {
  type        = string
  description = "Repositorio conectado al despliegue, formato owner/repo (sin https://)."
}

variable "git_branch_production" {
  type        = string
  default     = "main"
  description = "Rama que dispara despliegues del entorno production (Railway)."
}

variable "git_branch_staging" {
  type        = string
  default     = "staging"
  description = "Rama que dispara despliegues del entorno staging (Railway)."
}

variable "official_frontend_origin_production" {
  type        = string
  description = "Origen HTTPS del frontend en producción (OFFICIAL_FRONTEND_ORIGIN)."
}

variable "official_frontend_origin_staging" {
  type        = string
  description = "Origen HTTPS del frontend en staging (OFFICIAL_FRONTEND_ORIGIN)."
}

variable "supabase_url" {
  type        = string
  sensitive   = true
  description = "SUPABASE_URL (puede diferir entre staging y producción usando dos applies o ampliando el módulo)."
}

variable "supabase_key" {
  type        = string
  sensitive   = true
  description = "SUPABASE_KEY (anon o clave pública usada por el backend)."
}

variable "supabase_service_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "SUPABASE_SERVICE_KEY; si vacío, el backend puede caer en fallback (no recomendado en prod)."
}

variable "jwt_secret_key" {
  type        = string
  sensitive   = true
  description = "JWT_SECRET_KEY o equivalente (>= 32 caracteres recomendado)."
}

variable "session_secret_key" {
  type        = string
  sensitive   = true
  description = "SESSION_SECRET_KEY (cookies OAuth / sesión)."
}

variable "security_contact_email" {
  type        = string
  default     = "security@ablogistics-os.com"
  description = "Buzón para RFC 9116 (/.well-known/security.txt) y transparencia; debe existir en DNS/MX y estar monitorizado."
}

variable "maps_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Maps_API_KEY (Google Maps Platform, servidor)."
}

variable "database_url_production" {
  type        = string
  sensitive   = true
  description = "DATABASE_URL para production: URL completa o referencia Railway (sintaxis Service.VAR en docs/INFRASTRUCTURE.md)."
}

variable "database_url_staging" {
  type        = string
  sensitive   = true
  description = "DATABASE_URL para staging (misma convención que production)."
}

variable "redis_url_production" {
  type        = string
  sensitive   = true
  description = "REDIS_URL para production (referencia al plugin Redis o URL explícita)."
}

variable "redis_url_staging" {
  type        = string
  sensitive   = true
  description = "REDIS_URL para staging."
}

variable "cors_allow_origins_extra_production" {
  type        = string
  default     = ""
  description = "Opcional: orígenes extra coma-separados para CORS_ALLOW_ORIGINS en production."
}

variable "cors_allow_origins_extra_staging" {
  type        = string
  default     = ""
  description = "Opcional: orígenes extra para staging."
}
