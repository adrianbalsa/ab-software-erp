output "railway_project_id" {
  description = "ID del proyecto Railway."
  value       = railway_project.app.id
}

output "railway_production_environment_id" {
  description = "ID del entorno production (por defecto del proyecto)."
  value       = local.production_environment_id
}

output "railway_staging_environment_id" {
  description = "ID del entorno staging."
  value       = railway_environment.staging.id
}

output "service_ids" {
  description = "IDs de los cuatro servicios de cómputo (API + worker × entornos)."
  value = {
    backend_production  = railway_service.backend_production.id
    worker_production   = railway_service.worker_production.id
    backend_staging     = railway_service.backend_staging.id
    worker_staging      = railway_service.worker_staging.id
  }
}
