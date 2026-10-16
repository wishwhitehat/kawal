variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Firestore and Artifact Registry (Singapore keeps JAPAC data in-region)."
  type        = string
  default     = "asia-southeast1"
}

variable "live_location" {
  description = "Vertex AI location serving the Gemini Live model."
  type        = string
  default     = "us-central1"
}

variable "hosting_site_id" {
  description = "Firebase Hosting site ID (becomes <id>.web.app). Must be globally unique."
  type        = string
  default     = "kawal-ai"
}

variable "api_image" {
  description = "Container image for the API. Set by scripts/deploy.sh after Cloud Build."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "min_instances" {
  description = "Warm Cloud Run instances. 0 = scale to zero (near-zero cost; the web app pre-warms the API)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Upper bound on Cloud Run instances - also a cost guard-rail."
  type        = number
  default     = 2
}

variable "extra_origins" {
  description = "Additional browser origins allowed by CORS (e.g. a custom domain)."
  type        = list(string)
  default     = []
}

variable "billing_account" {
  description = "Billing account ID for the budget alert. Leave empty to skip."
  type        = string
  default     = ""
}

variable "budget_amount" {
  description = "Monthly budget in the billing account's currency. Alerts at 25/50/75/90/100% and the kill switch engages at 100%."
  type        = number
  default     = 20
}

variable "alert_email" {
  description = "E-mail for budget, downtime, breaker and abuse alerts. Keep it in terraform.tfvars."
  type        = string
  default     = ""
}

variable "appcheck_enforce" {
  description = "Enforce Firebase App Check on Firestore and Auth, and require it on the API."
  type        = bool
  default     = true
}

variable "appcheck_debug_token" {
  description = "Optional App Check debug token (UUID) for CI / headless demo recording. Secret - tfvars only."
  type        = string
  default     = ""
  sensitive   = true
}

variable "global_daily" {
  description = "Daily ceilings across ALL users - the hard cap on model spend."
  type        = map(number)
  default     = { check = 150, grounding = 60, live = 25, tts = 40, ask = 60, bulletin = 8 }
}

variable "user_daily" {
  description = "Daily per-user (Firebase uid) limits."
  type        = map(number)
  default     = { check = 20, live = 5, tts = 10, ask = 15, bulletin = 3 }
}

variable "ip_daily" {
  description = "Daily per-IP limits (IPs are stored only as keyed hashes)."
  type        = map(number)
  default     = { check = 40, live = 10, tts = 20, ask = 30, bulletin = 5 }
}
