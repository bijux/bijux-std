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
UI_TESTS_DIR ?= tests/bijux-docs

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

.PHONY: ui-test-install
ui-test-install: ## Install UI regression test dependencies
	@npm --prefix "$(UI_TESTS_DIR)" install

.PHONY: ui-test-install-browsers
ui-test-install-browsers: ## Install browser runtime for UI regression tests
	@npm --prefix "$(UI_TESTS_DIR)" run install:browsers

.PHONY: ui-test
ui-test: ## Run responsive UI/UX regression checks (phone/normal/wide)
	@npm --prefix "$(UI_TESTS_DIR)" run test:ui

.PHONY: ui-test-navigation
ui-test-navigation: ## Run navigation regression checks only
	@npm --prefix "$(UI_TESTS_DIR)" run test:ui -- ui/specs/navigation-regression.spec.js

.PHONY: ui-test-release-gate
ui-test-release-gate: ## Run navigation release-gate checks (core + quality suites)
	@npm --prefix "$(UI_TESTS_DIR)" run test:ui -- ui/specs/navigation-regression.spec.js ui/specs/navigation-release-quality.spec.js

.PHONY: ui-test-live-navigation
ui-test-live-navigation: ## Run live-site navigation release checks (set BIJUX_LIVE_E2E=1)
	@BIJUX_LIVE_E2E="$${BIJUX_LIVE_E2E:-0}" npm --prefix "$(UI_TESTS_DIR)" run test:ui:live-navigation
