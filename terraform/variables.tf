variable "atlas_public_key" {
  description = "Public API Key de MongoDB Atlas"
  type        = string
}

variable "atlas_private_key" {
  description = "Private API Key de MongoDB Atlas"
  type        = string
  sensitive   = true
}

variable "project_id" {
  description = "ID del proyecto en MongoDB Atlas"
  type        = string
}

variable "cluster_name" {
  description = "Nombre del cluster"
  type        = string
  default     = "Cluster0"
}

variable "db_username" {
  description = "Usuario de la base de datos"
  type        = string
  default     = "stivenmoreno725_db_user"
}

variable "db_password" {
  description = "Contrasena del usuario de la base de datos"
  type        = string
  sensitive   = true
}