resource "google_firebase_project" "this" {
  provider   = google-beta
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

resource "google_firebase_web_app" "web" {
  provider        = google-beta
  display_name    = "Kawal Web"
  deletion_policy = "DELETE"
  depends_on      = [google_firebase_project.this]
}

data "google_firebase_web_app_config" "web" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.web.app_id
}

resource "google_firebase_hosting_site" "web" {
  provider   = google-beta
  site_id    = var.hosting_site_id
  app_id     = google_firebase_web_app.web.app_id
  depends_on = [google_firebase_project.this]
}

# Firebase Authentication (Identity Platform): anonymous sign-in for citizens,
# restricted to our own domains.
resource "google_identity_platform_config" "auth" {
  autodelete_anonymous_users = true

  sign_in {
    anonymous {
      enabled = true
    }
    # Declared explicitly (disabled) so the plan has no drift.
    email {
      enabled           = false
      password_required = false
    }
    phone_number {
      enabled = false
    }
  }

  authorized_domains = concat(
    ["localhost", "${var.project_id}.firebaseapp.com", "${var.project_id}.web.app"],
    [for o in local.hosting_origins : trimprefix(o, "https://")],
  )
  depends_on = [google_firebase_project.this]
}

# A browser API key locked to our hosting origins and to the Firebase APIs we use.
resource "google_apikeys_key" "web" {
  name         = "kawal-web"
  display_name = "Kawal web (restricted)"

  restrictions {
    browser_key_restrictions {
      allowed_referrers = concat([for o in local.allowed_origins : "${o}/*"])
    }
    api_targets {
      service = "identitytoolkit.googleapis.com"
    }
    api_targets {
      service = "securetoken.googleapis.com"
    }
    api_targets {
      service = "firestore.googleapis.com"
    }
    api_targets {
      service = "firebaseinstallations.googleapis.com"
    }
  }
  depends_on = [google_project_service.apis]
}
