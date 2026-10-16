# Cost & abuse guard-rails for a public, open-source deployment.
#
#   App Check        only our genuine web app (reCAPTCHA Enterprise attested) can call
#                    the API, read Firestore or create anonymous accounts.
#   Budget breaker   Cloud Billing budget -> Pub/Sub -> kawal-api /internal/budget,
#                    which flips a kill switch that pauses every AI feature.
#   Alerts           e-mail on budget thresholds, downtime, breaker trips, abuse spikes.
#
# Daily per-feature ceilings live in the app (backend/app/guard.py) and are set
# from var.global_daily / user_daily / ip_daily below.

# ----------------------------------------------------------------- App Check
resource "google_recaptcha_enterprise_key" "web" {
  display_name = "kawal-web"

  web_settings {
    integration_type  = "SCORE" # invisible - no user challenge
    allow_all_domains = false
    allowed_domains   = concat([for o in local.hosting_origins : trimprefix(o, "https://")], ["localhost"])
  }
  depends_on = [google_project_service.apis]
}

resource "google_firebase_app_check_recaptcha_enterprise_config" "web" {
  provider  = google-beta
  app_id    = google_firebase_web_app.web.app_id
  site_key  = google_recaptcha_enterprise_key.web.name
  token_ttl = "3600s"
}

# Enforce App Check on the Firebase services the browser talks to directly.
resource "google_firebase_app_check_service_config" "enforced" {
  provider         = google-beta
  for_each         = var.appcheck_enforce ? toset(["firestore.googleapis.com", "identitytoolkit.googleapis.com"]) : toset([])
  service_id       = each.value
  enforcement_mode = "ENFORCED"
  depends_on       = [google_firebase_app_check_recaptcha_enterprise_config.web]
}

# Optional debug token for CI / headless demo recording (keep it in terraform.tfvars, never in git).
resource "google_firebase_app_check_debug_token" "ci" {
  provider     = google-beta
  count        = var.appcheck_debug_token == "" ? 0 : 1
  app_id       = google_firebase_web_app.web.app_id
  display_name = "ci-and-demo-recording"
  token        = var.appcheck_debug_token
}

# ----------------------------------------------------------------- budget circuit breaker
resource "google_pubsub_topic" "budget" {
  name       = "kawal-budget"
  depends_on = [google_project_service.apis]
}

# Cloud Billing publishes budget notifications as this Google-managed identity.
resource "google_pubsub_topic_iam_member" "billing_publisher" {
  topic  = google_pubsub_topic.budget.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:billing-budget-alert@system.gserviceaccount.com"
}

# Identity Pub/Sub uses to sign (OIDC) its pushes; the API accepts only this caller.
resource "google_service_account" "budget_push" {
  account_id   = "kawal-budget-push"
  display_name = "Kawal budget breaker (Pub/Sub push identity)"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.budget_push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "budget_breaker" {
  name                       = "kawal-budget-breaker"
  topic                      = google_pubsub_topic.budget.id
  ack_deadline_seconds       = 30
  message_retention_duration = "86400s"

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.api.uri}/internal/budget"
    oidc_token {
      service_account_email = google_service_account.budget_push.email
      audience              = local.budget_audience
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# ----------------------------------------------------------------- alerting
resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email == "" ? 0 : 1
  display_name = "Kawal owner e-mail"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
  depends_on = [google_project_service.apis]
}

locals {
  alert_channels  = [for c in google_monitoring_notification_channel.email : c.id]
  budget_audience = "kawal-budget-breaker"
  run_logs        = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_v2_service.api.name}\""
}

resource "google_logging_metric" "quota_rejections" {
  name   = "kawal_quota_rejections"
  filter = "${local.run_logs} AND textPayload:\"quota_exceeded\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "breaker_trips" {
  name   = "kawal_breaker_trips"
  filter = "${local.run_logs} AND textPayload:\"kawal_paused\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "abuse_spike" {
  display_name          = "Kawal - abuse spike (quota rejections)"
  combiner              = "OR"
  notification_channels = local.alert_channels
  conditions {
    display_name = "More than 30 quota rejections in an hour"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.quota_rejections.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 30
      duration        = "0s"
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  documentation {
    content = "Someone is hitting Kawal's daily quotas repeatedly. Check Cloud Run logs for 'quota_exceeded'. Daily ceilings still cap spend."
  }
}

resource "google_monitoring_alert_policy" "breaker" {
  display_name          = "Kawal - budget breaker engaged (AI paused)"
  combiner              = "OR"
  notification_channels = local.alert_channels
  conditions {
    display_name = "Kill switch engaged"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.breaker_trips.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  documentation {
    content = "The monthly budget was reached and Kawal paused its AI features. To resume: raise var.budget_amount and re-apply, or set Firestore config/runtime.paused=false."
  }
}

resource "google_monitoring_alert_policy" "uptime" {
  display_name          = "Kawal - API health check failing"
  combiner              = "OR"
  notification_channels = local.alert_channels
  conditions {
    display_name = "Uptime check failed"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.api.uptime_check_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "900s"
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }
}
