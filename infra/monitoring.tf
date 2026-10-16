resource "google_monitoring_uptime_check_config" "api" {
  display_name = "kawal-api health"
  timeout      = "10s"
  period       = "300s"

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

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  depends_on = [google_project_service.apis]
}
