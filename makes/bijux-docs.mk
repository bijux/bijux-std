UI_TESTS_DIR ?= tests/bijux-docs

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
