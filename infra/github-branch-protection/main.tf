data "github_repository" "protected" {
  for_each = var.protected_repositories

  full_name = "${var.github_owner}/${each.value}"
}

resource "github_branch_protection" "main" {
  for_each = data.github_repository.protected

  repository_id = each.value.name
  pattern       = "main"

  enforce_admins                 = true
  allows_force_pushes            = false
  allows_deletions               = false
  require_conversation_resolution = true
  required_linear_history        = false

  required_pull_request_reviews {
    dismiss_stale_reviews           = false
    require_code_owner_reviews      = false
    require_last_push_approval      = false
    required_approving_review_count = var.required_approving_review_count
  }
}
