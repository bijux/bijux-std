UI_TESTS_DIR ?= tests/bijux-docs
BIJUX_DOCS_ARTIFACTS_DIR ?= artifacts/bijux-docs
UI_TESTS_RUNTIME_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)
UI_TESTS_NPM_CACHE_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/npm-cache
UI_TESTS_PLAYWRIGHT_BROWSERS_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/playwright/browsers
UI_TESTS_PACKAGE_JSON ?= $(UI_TESTS_DIR)/package.json
UI_TESTS_PACKAGE_LOCK ?= $(UI_TESTS_DIR)/package-lock.json
UI_TESTS_RUNTIME_PACKAGE_JSON ?= $(UI_TESTS_RUNTIME_DIR)/package.json
UI_TESTS_RUNTIME_PACKAGE_LOCK ?= $(UI_TESTS_RUNTIME_DIR)/package-lock.json

.PHONY: ui-test-prepare-runtime
ui-test-prepare-runtime:
	@mkdir -p "$(UI_TESTS_RUNTIME_DIR)" "$(UI_TESTS_NPM_CACHE_DIR)" "$(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR)"
	@cp "$(UI_TESTS_PACKAGE_JSON)" "$(UI_TESTS_RUNTIME_PACKAGE_JSON)"
	@cp "$(UI_TESTS_PACKAGE_LOCK)" "$(UI_TESTS_RUNTIME_PACKAGE_LOCK)"

.PHONY: ui-test-install
ui-test-install: ui-test-prepare-runtime ## Install UI regression test dependencies
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" ci

.PHONY: ui-test-install-browsers
ui-test-install-browsers: ui-test-prepare-runtime ## Install browser runtime for UI regression tests
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright install chromium

.PHONY: ui-test
ui-test: ui-test-prepare-runtime ## Run responsive UI/UX regression checks (phone/normal/wide)
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.config.js"

.PHONY: ui-test-navigation
ui-test-navigation: ui-test-prepare-runtime ## Run navigation regression checks only
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.config.js" "$(UI_TESTS_DIR)/ui/specs/navigation-regression.spec.js"

.PHONY: ui-test-release-gate
ui-test-release-gate: ui-test-prepare-runtime ## Run navigation release-gate checks (core + quality suites)
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.config.js" "$(UI_TESTS_DIR)/ui/specs/navigation-regression.spec.js" "$(UI_TESTS_DIR)/ui/specs/navigation-release-quality.spec.js"

.PHONY: ui-test-live-navigation
ui-test-live-navigation: ui-test-prepare-runtime ## Run live-site navigation release checks (set BIJUX_LIVE_E2E=1)
	@BIJUX_LIVE_E2E="$${BIJUX_LIVE_E2E:-0}" NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.config.js" "$(UI_TESTS_DIR)/ui/specs/navigation-live-e2e.spec.js"
