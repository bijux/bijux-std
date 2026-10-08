UI_TESTS_DIR ?= tests/bijux-docs
BIJUX_DOCS_ARTIFACTS_DIR ?= artifacts/bijux-docs
UI_TESTS_RUNTIME_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/node-runtime
UI_TESTS_NPM_CACHE_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/npm-cache
UI_TESTS_PLAYWRIGHT_BROWSERS_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/playwright/browsers
UI_TESTS_PYTHON_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/python
UI_TESTS_PIP_CACHE_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/pip-cache
UI_TESTS_PACKAGE_JSON ?= $(UI_TESTS_DIR)/package.json
UI_TESTS_PACKAGE_LOCK ?= $(UI_TESTS_DIR)/package-lock.json
UI_TESTS_RUNTIME_PACKAGE_JSON ?= $(UI_TESTS_RUNTIME_DIR)/package.json
UI_TESTS_RUNTIME_PACKAGE_LOCK ?= $(UI_TESTS_RUNTIME_DIR)/package-lock.json
UI_TESTS_NODE_MODULES_LINK ?= $(UI_TESTS_DIR)/node_modules
UI_TESTS_NODE_MODULES_TARGET = $(abspath $(UI_TESTS_RUNTIME_DIR))/node_modules

.PHONY: docs-theme-tests
docs-theme-tests: ## Check shared palette persistence without browser dependencies
	@command -v node >/dev/null 2>&1 || { echo "node 18 or later is required" >&2; exit 1; }
	@node --test "$(UI_TESTS_DIR)/unit/theme-persistence.test.js"

.PHONY: ui-test-prepare-runtime
ui-test-prepare-runtime:
	@mkdir -p "$(UI_TESTS_RUNTIME_DIR)" "$(UI_TESTS_NPM_CACHE_DIR)" "$(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR)"
	@cp "$(UI_TESTS_PACKAGE_JSON)" "$(UI_TESTS_RUNTIME_PACKAGE_JSON)"
	@cp "$(UI_TESTS_PACKAGE_LOCK)" "$(UI_TESTS_RUNTIME_PACKAGE_LOCK)"
	@if [ -e "$(UI_TESTS_NODE_MODULES_LINK)" ] && [ ! -L "$(UI_TESTS_NODE_MODULES_LINK)" ]; then \
		echo "ERROR: preserve existing node_modules; move it explicitly before preparing artifact runtime" >&2; exit 1; \
	fi
	@if [ -L "$(UI_TESTS_NODE_MODULES_LINK)" ] && [ "$$(cd "$(UI_TESTS_DIR)" && cd "$$(readlink node_modules)" && pwd)" != "$(UI_TESTS_NODE_MODULES_TARGET)" ]; then \
		echo "ERROR: node_modules points to another runtime; resolve it explicitly" >&2; exit 1; \
	fi
	@if [ ! -e "$(UI_TESTS_NODE_MODULES_LINK)" ] && [ ! -L "$(UI_TESTS_NODE_MODULES_LINK)" ]; then \
		ln -s "$(UI_TESTS_NODE_MODULES_TARGET)" "$(UI_TESTS_NODE_MODULES_LINK)"; \
	fi

.PHONY: ui-test-install
ui-test-install: ui-test-prepare-runtime ## Install the exact browser-test lock into artifacts
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" ci

.PHONY: ui-test-install-browsers
ui-test-install-browsers: ui-test-prepare-runtime ## Install admitted Chromium, Firefox and WebKit into artifacts
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright install chromium firefox webkit

.PHONY: ui-test-install-docs
ui-test-install-docs: ## Install the admitted strict fixture renderer into artifacts
	@mkdir -p "$(UI_TESTS_PIP_CACHE_DIR)"
	@python3 -m venv "$(UI_TESTS_PYTHON_DIR)"
	@"$(UI_TESTS_PYTHON_DIR)/bin/python" -m pip install --cache-dir "$(UI_TESTS_PIP_CACHE_DIR)" -r "$(UI_TESTS_DIR)/generated/requirements.lock.txt"

.PHONY: ui-test-fixtures
ui-test-fixtures: ## Render the full canonical shared shell through real MkDocs/Material
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_TESTS_PYTHON_DIR)/bin/python" "$(UI_TESTS_DIR)/generated/build.py"

.PHONY: ui-test-unit
ui-test-unit: ## Check meaningful isolated runtime invariants
	@node --test "$(UI_TESTS_DIR)"/unit/*.test.js
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_TESTS_PYTHON_DIR)/bin/python" -m unittest discover -s "$(UI_TESTS_DIR)/generated" -p test_navigation_projection.py

.PHONY: ui-test
ui-test: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify generated shell in all nine engine/profile projects
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.config.js"

.PHONY: ui-test-navigation
ui-test-navigation: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify the bounded navigation matrix with real Material search
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.navigation.config.js"
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/drawer-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.drawer.config.js"

.PHONY: ui-test-release-gate
ui-test-release-gate: ui-test ## Required generated browser, responsive and runtime gate

.PHONY: ui-test-live-navigation
ui-test-live-navigation: ui-test-prepare-runtime ## Run ordinary read-only published journeys with BIJUX_LIVE_E2E=1
	@BIJUX_LIVE_E2E="$${BIJUX_LIVE_E2E:-0}" NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.live.config.js"
