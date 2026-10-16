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
  description = "Warm Cloud Run instances (1 avoids cold starts during judging)."
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Upper bound on Cloud Run instances - also a cost guard-rail."
  type        = number
  default     = 4
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
  description = "Monthly budget, in the billing account's own currency, that triggers alert e-mails to billing admins."
  type        = number
  default     = 200
}
