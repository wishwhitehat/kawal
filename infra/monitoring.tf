resource "google_monitoring_uptime_check_config" "api" {
  display_name = "kawal-api health"
  timeout      = "10s"
  period       = "900s" # every 15 min keeps scale-to-zero cheap

  http_check {
    path         = "/api/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = trimprefix(google_cloud_run_v2_service.api.uri, "https://")
    }
  }
  depends_on = [google_project_service.apis]
}

# Monthly budget in the billing account's currency. Every update is published to
# Pub/Sub (-> circuit breaker in guardrails.tf) and threshold e-mails go to billing
# admins plus var.alert_email.
resource "google_billing_budget" "kawal" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "kawal-${var.project_id}"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      units = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.25, 0.5, 0.75, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    pubsub_topic                     = google_pubsub_topic.budget.id
    schema_version                   = "1.0"
    monitoring_notification_channels = local.alert_channels
    disable_default_iam_recipients   = false
  }

  depends_on = [google_pubsub_topic_iam_member.billing_publisher]
}
