SHELL := /bin/sh
.SHELLFLAGS := -eu -c
.DEFAULT_GOAL := help

BIJUX_STD_CHECK_SCRIPT ?= shared/bijux-checks/check-bijux-std.sh
BIJUX_STD_UPDATE_SCRIPT ?= shared/bijux-checks/update-bijux-std.sh
BIJUX_STD_REF ?= main
BIJUX_STD_REMOTE ?= https://github.com/bijux/bijux-std
BIJUX_STD_GIT_URL ?= https://github.com/bijux/bijux-std.git
BIJUX_STD_UPDATE_CHANNEL ?= branch
BIJUX_STD_TAG_PATTERN ?= v*

.PHONY: help
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: bijux-std-checks
bijux-std-checks: ## Verify shared directories match bijux-std (set BIJUX_STD_REF for pinning)
	@BIJUX_STD_REF="$(BIJUX_STD_REF)" BIJUX_STD_REMOTE="$(BIJUX_STD_REMOTE)" bash "$(BIJUX_STD_CHECK_SCRIPT)"

.PHONY: bijux-std-update
bijux-std-update: ## Update shared directories from bijux-std (set BIJUX_STD_UPDATE_CHANNEL=branch|tag)
	@BIJUX_STD_REF="$(BIJUX_STD_REF)" BIJUX_STD_GIT_URL="$(BIJUX_STD_GIT_URL)" BIJUX_STD_UPDATE_CHANNEL="$(BIJUX_STD_UPDATE_CHANNEL)" BIJUX_STD_TAG_PATTERN="$(BIJUX_STD_TAG_PATTERN)" bash "$(BIJUX_STD_UPDATE_SCRIPT)"

.PHONY: bijux-std
bijux-std: bijux-std-checks ## Backward-compatible alias
