#!/usr/bin/env bash
# Classify authored checkouts by identity and layout; revision acceptance is separate.
is_standard_source_checkout() {
  local root="$1" remote
  [[ -f "${root}/shared/shared-dir-sha256.txt" && -d "${root}/shared/bijux-checks" ]] || return 1
  remote="$(git -C "${root}" remote get-url origin 2>/dev/null)" || return 1
  case "${remote}" in
    https://gitlab.com/bijux-oss/bijux-std|https://gitlab.com/bijux-oss/bijux-std.git) return 0 ;;
    git@gitlab.com:bijux-oss/bijux-std|git@gitlab.com:bijux-oss/bijux-std.git) return 0 ;;
    ssh://git@gitlab.com/bijux-oss/bijux-std.git|ssh://git@gitlab.com:22/bijux-oss/bijux-std.git) return 0 ;;
    https://github.com/bijux/bijux-std|https://github.com/bijux/bijux-std.git|git@github.com:bijux/bijux-std|git@github.com:bijux/bijux-std.git) return 0 ;;
    *) return 1 ;;
  esac
}
