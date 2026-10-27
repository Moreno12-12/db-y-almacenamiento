terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.0"
    }
  }
  required_version = ">= 1.0"
}

provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}

resource "mongodbatlas_cluster" "urbanrush" {
  project_id   = var.project_id
  name         = var.cluster_name
  cluster_type = "REPLICASET"

  provider_name               = "AWS"
  provider_instance_size_name = "M0"
  provider_region_name        = "US_EAST_1"

  replication_specs {
    num_shards = 1
    regions_config {
      region_name     = "US_EAST_1"
      electable_nodes = 3
      priority        = 7
      read_only_nodes = 0
    }
  }
}

resource "mongodbatlas_database_user" "urbanrush_user" {
  project_id         = var.project_id
  username           = var.db_username
  password           = var.db_password
  auth_database_name = "admin"

  roles {
    role_name     = "readWriteAnyDatabase"
    database_name = "admin"
  }
}

resource "mongodbatlas_project_ip_access_list" "acceso_ip" {
  project_id = var.project_id
  cidr_block = "0.0.0.0/0"
  comment    = "Acceso desde cualquier IP (academico)"
}