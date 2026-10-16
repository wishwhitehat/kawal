output "api_url" {
  description = "Cloud Run API base URL."
  value       = google_cloud_run_v2_service.api.uri
}

output "hosting_url" {
  description = "Public web app URL."
  value       = local.hosting_origins[0]
}

output "artifact_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.kawal.repository_id}"
}

output "hosting_site_id" {
  value = google_firebase_hosting_site.web.site_id
}

# Public client identifiers (not secrets) consumed by the web build.
output "firebase_web_config" {
  value = {
    apiKey     = google_apikeys_key.web.key_string
    authDomain = "${var.project_id}.firebaseapp.com"
    projectId  = var.project_id
    appId      = google_firebase_web_app.web.app_id
  }
  sensitive = true
}
