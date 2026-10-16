resource "google_cloud_run_v2_service" "api" {
  name                = "kawal-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.api.email
    timeout                          = "3600s" # long-lived WebSockets for Live Guardian
    max_instance_request_concurrency = 40
    session_affinity                 = true

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LIVE_LOCATION"
        value = var.live_location
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = join(",", local.allowed_origins)
      }
      env {
        name = "INDICATOR_PEPPER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.pepper.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
        }
        initial_delay_seconds = 2
        period_seconds        = 3
        failure_threshold     = 10
      }
    }
  }

  depends_on = [
    google_project_iam_member.api,
    google_secret_manager_secret_iam_member.api_pepper,
    google_secret_manager_secret_version.pepper,
  ]
}

# Public endpoint: the app authenticates every call itself with Firebase ID tokens.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
