locals {
  apis = [
    "aiplatform.googleapis.com",
    "apikeys.googleapis.com",
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebaseappcheck.googleapis.com",
    "firebasehosting.googleapis.com",
    "firebaserules.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "identitytoolkit.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "recaptchaenterprise.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "securetoken.googleapis.com",
    "serviceusage.googleapis.com",
    "webrisk.googleapis.com",
  ]

  hosting_origins = [
    "https://${var.hosting_site_id}.web.app",
    "https://${var.hosting_site_id}.firebaseapp.com",
  ]
  allowed_origins = concat(local.hosting_origins, ["http://localhost:5173"], var.extra_origins)
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ----------------------------------------------------------------- identities
resource "google_service_account" "api" {
  account_id   = "kawal-api"
  display_name = "Kawal API (Cloud Run runtime)"
  depends_on   = [google_project_service.apis]
}

locals {
  api_roles = [
    "roles/aiplatform.user",                   # Gemini on Vertex AI
    "roles/datastore.user",                    # Firestore read/write
    "roles/serviceusage.serviceUsageConsumer", # quota attribution (incl. Web Risk Lookup API)
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
  ]
  # Cloud Build runs as the default compute SA in new projects.
  build_sa    = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
  build_roles = ["roles/artifactregistry.writer", "roles/logging.logWriter", "roles/storage.objectViewer"]
}

resource "google_project_iam_member" "api" {
  for_each = toset(local.api_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "build" {
  for_each   = toset(local.build_roles)
  project    = var.project_id
  role       = each.value
  member     = local.build_sa
  depends_on = [google_project_service.apis]
}

# ----------------------------------------------------------------- secrets
# Pepper for HMAC fingerprints of phone numbers / accounts. Generated here,
# stored only in Secret Manager (and the private, encrypted state bucket).
resource "random_password" "pepper" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret" "pepper" {
  secret_id = "kawal-indicator-pepper"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "pepper" {
  secret      = google_secret_manager_secret.pepper.id
  secret_data = random_password.pepper.result
}

resource "google_secret_manager_secret_iam_member" "api_pepper" {
  secret_id = google_secret_manager_secret.pepper.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# ----------------------------------------------------------------- registry
resource "google_artifact_registry_repository" "kawal" {
  location      = var.region
  repository_id = "kawal"
  format        = "DOCKER"
  description   = "Kawal container images"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
  depends_on = [google_project_service.apis]
}
