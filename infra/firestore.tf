resource "google_firestore_database" "default" {
  name                    = "(default)"
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  concurrency_mode        = "OPTIMISTIC"
  delete_protection_state = "DELETE_PROTECTION_ENABLED"
  deletion_policy         = "ABANDON"
  depends_on              = [google_project_service.apis]
}

# KNN vector index for campaign clustering and semantic search (Gemini embeddings, 768-d).
resource "google_firestore_index" "reports_embedding" {
  database    = google_firestore_database.default.name
  collection  = "reports"
  query_scope = "COLLECTION"

  # Firestore stores vector indexes with an implicit __name__ field; declaring it
  # avoids a perpetual diff that would force Terraform to replace the index.
  fields {
    field_path = "__name__"
    order      = "ASCENDING"
  }
  fields {
    field_path = "embedding"
    vector_config {
      dimension = 768
      flat {}
    }
  }
}

resource "google_firestore_index" "campaigns_by_type" {
  database   = google_firestore_database.default.name
  collection = "campaigns"

  fields {
    field_path = "scamType"
    order      = "ASCENDING"
  }
  fields {
    field_path = "count"
    order      = "DESCENDING"
  }
}

# Data minimisation: reports expire after 180 days, ticker items after 30 days.
resource "google_firestore_field" "reports_ttl" {
  database   = google_firestore_database.default.name
  collection = "reports"
  field      = "expireAt"
  ttl_config {}
  index_config {}
}

resource "google_firestore_field" "feed_ttl" {
  database   = google_firestore_database.default.name
  collection = "feed"
  field      = "expireAt"
  ttl_config {}
  index_config {}
}

# Security rules: browsers may only READ aggregated, redacted collections.
# All writes go through the API (Admin SDK), which bypasses rules.
resource "google_firebaserules_ruleset" "firestore" {
  provider = google-beta
  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../firebase/firestore.rules")
    }
  }
  depends_on = [google_firestore_database.default]
}

resource "google_firebaserules_release" "firestore" {
  provider     = google-beta
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name
  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }
}

# TTL for quota counters (usage/{day} + per-user / per-IP sub-collections) and the result cache.
resource "google_firestore_field" "ttl" {
  for_each   = toset(["usage", "users", "ips", "cache"])
  database   = google_firestore_database.default.name
  collection = each.value
  field      = "expireAt"
  ttl_config {}
  index_config {}
}
