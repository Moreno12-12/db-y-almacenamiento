output "cluster_connection_string" {
  description = "Cadena de conexion mongodb+srv del cluster"
  value       = "mongodb+srv://${var.db_username}:${var.db_password}@${mongodbatlas_cluster.urbanrush.srv_address}/?retryWrites=true&w=majority"
  sensitive   = true
}

output "cluster_id" {
  description = "ID del cluster"
  value       = mongodbatlas_cluster.urbanrush.cluster_id
}

output "cluster_info" {
  description = "Informacion resumida del cluster (para el dashboard del informe)"
  value = {
    backup      = mongodbatlas_cluster.urbanrush.backup_enabled
    disk_gb     = try(mongodbatlas_cluster.urbanrush.disk_size_gb, 0)
    instance    = mongodbatlas_cluster.urbanrush.provider_instance_size_name
    name        = mongodbatlas_cluster.urbanrush.name
    provider    = mongodbatlas_cluster.urbanrush.provider_name
    region      = mongodbatlas_cluster.urbanrush.provider_region_name
    replication = "3 nodos (REPLICASET)"
  }
}

output "cluster_state" {
  description = "Estado del cluster"
  value       = mongodbatlas_cluster.urbanrush.state_name
}

output "database_username" {
  description = "Usuario de la base de datos"
  value       = var.db_username
}

output "project_id" {
  description = "ID del proyecto Atlas"
  value       = mongodbatlas_cluster.urbanrush.project_id
}