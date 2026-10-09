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
	@node --test "$(UI_TESTS_DIR)"/unit/*.test.js "$(UI_TESTS_DIR)"/unit/*.test.cjs
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_TESTS_PYTHON_DIR)/bin/python" -m unittest discover -s "$(UI_TESTS_DIR)/generated" -p "test_*.py"

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

.PHONY: ui-test-preferences
ui-test-preferences: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify storage failure and palette recovery in three phone engines
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/preferences-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.preferences.config.js"

.PHONY: ui-test-diagrams
ui-test-diagrams: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify single-owner self-hosted diagrams across three engines
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/diagram-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.diagrams.config.js"

.PHONY: ui-test-repository
ui-test-repository: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify optional repository facts and ordinary native navigation
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/repository-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.repository.config.js"

.PHONY: ui-test-search
ui-test-search: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify native query and recovery in three phone engines
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search.config.js"

.PHONY: ui-test-content
ui-test-content: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify authored Material content in every engine and viewport
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/content-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.content.config.js"

.PHONY: ui-test-native-navigation
ui-test-native-navigation: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify native drawer fallback, readiness and controlled faults in three engines
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/native-navigation-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.native-navigation.config.js"

.PHONY: ui-test-reader
ui-test-reader: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify wide reader content, source preservation and document disposal
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/reader-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.reader.config.js"

.PHONY: ui-test-contrast
ui-test-contrast: ui-test-prepare-runtime ## Qualify shared text, focus and hit targets in nine engine/profile projects
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_TESTS_PYTHON_DIR)/bin/python" "$(UI_TESTS_DIR)/generated/build.py" --output "$(BIJUX_DOCS_ARTIFACTS_DIR)/contrast-generated" --base-url "http://127.0.0.1:62599"
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_GENERATED_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/contrast-generated" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/contrast-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.contrast.config.js"

.PHONY: ui-test-search-invoker
ui-test-search-invoker: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify modal and native inline search invocation, keyboard defaults and header reachability
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-invoker-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-invoker.config.js"

BIJUX_LINK_POLICY_ORIGIN ?= http://127.0.0.1:4173

.PHONY: ui-test-link-policy
ui-test-link-policy: ui-test-prepare-runtime ## Qualify authored link intent, native journeys and document annotation ownership
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_TESTS_PYTHON_DIR)/bin/python" "$(UI_TESTS_DIR)/generated/build.py" --output "$(BIJUX_DOCS_ARTIFACTS_DIR)/link-policy-generated" --base-url "$(BIJUX_LINK_POLICY_ORIGIN)"
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_LINK_POLICY_ORIGIN="$(BIJUX_LINK_POLICY_ORIGIN)" BIJUX_GENERATED_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/link-policy-generated" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/link-policy-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.links.config.js"

.PHONY: ui-test-history
ui-test-history: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify history through ordinary generated Material journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/history-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.history.config.js"

.PHONY: ui-test-registry-overflow
ui-test-registry-overflow: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify bounded desktop registry pointer keyboard and touch journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/registry-overflow-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.registry-overflow.config.js"

.PHONY: ui-test-native-reader-history
ui-test-native-reader-history: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify native diagram restoration, instant continuity and trusted input
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/native-reader-history-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.native-reader-history.config.js"

.PHONY: ui-test-publication-commands
ui-test-publication-commands: ## Qualify the exact installed renderer command boundaries separately from browser fixtures
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(UI_TESTS_DIR)/execution/publication_gate.py" run --python "$(UI_TESTS_PYTHON_DIR)/bin/python" --output "$(BIJUX_DOCS_ARTIFACTS_DIR)/publication-commands"

.PHONY: ui-test-search-reflow-phone
ui-test-search-reflow-phone: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify search reflow phone through ordinary generated Material journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-reflow-phone-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-reflow-phone.config.js"

.PHONY: ui-test-search-reflow-tablet
ui-test-search-reflow-tablet: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify search reflow tablet through ordinary generated Material journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-reflow-tablet-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-reflow-tablet.config.js"

.PHONY: ui-test-search-reflow-desktop
ui-test-search-reflow-desktop: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify search reflow desktop through ordinary generated Material journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-reflow-desktop-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-reflow-desktop.config.js"

.PHONY: ui-test-popup-relationships
ui-test-popup-relationships: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify popup identity, dialog semantics and document disposal
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/popup-relationships-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.popup-relationships.config.js"

.PHONY: ui-test-search-scope
ui-test-search-scope: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify site-local native search descriptions and reader journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-scope-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-scope.config.js"

.PHONY: ui-test-reader-accessibility
ui-test-reader-accessibility: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify keyboard drawer and reader focus journeys
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/reader-accessibility-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.reader-accessibility.config.js"

.PHONY: ui-test-diagram-trust
ui-test-diagram-trust: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify scientific diagram meaning and renderer trust boundaries
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/diagram-trust-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.diagram-trust.config.js"

.PHONY: ui-test-accessibility-state
ui-test-accessibility-state: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Scan actual document drawer and search accessibility states
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/accessibility-state-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.accessibility-state.config.js"

.PHONY: ui-test-search-shortcut-modality
ui-test-search-shortcut-modality: ui-test-prepare-runtime ui-test-fixtures ui-test-unit ## Qualify literal reader input and explicit native search invocation
	@NPM_CONFIG_CACHE="$(abspath $(UI_TESTS_NPM_CACHE_DIR))" PLAYWRIGHT_BROWSERS_PATH="$(abspath $(UI_TESTS_PLAYWRIGHT_BROWSERS_DIR))" BIJUX_UI_ARTIFACT_ROOT="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/search-shortcut-modality-playwright" BIJUX_UI_FULL_GATE=1 npm --prefix "$(UI_TESTS_RUNTIME_DIR)" exec -- playwright test --config "$(UI_TESTS_DIR)/playwright.search-shortcut-modality.config.js"


UI_CATALOGUE_PYTHON_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/python
UI_CATALOGUE_UV ?= uv
UI_CATALOGUE_BASE_PYTHON ?= python3
UI_CATALOGUE_INTERPRETER_DIR ?= $(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/interpreter
UI_CATALOGUE_GROUP ?= all

.PHONY: ui-test-install-catalogue-interpreter ui-test-install-catalogue ui-test-install-catalogue-default ui-test-catalogue
ui-test-install-catalogue-interpreter: ## Install the exact standalone catalogue verification interpreter
	@PYTHONDONTWRITEBYTECODE=1 python3 "$(UI_TESTS_DIR)/catalogue/python_runtime.py" --root "$(UI_CATALOGUE_INTERPRETER_DIR)" --uv "$(UI_CATALOGUE_UV)"

ui-test-install-catalogue: ## Install the exact independent catalogue verification lock
	@"$(UI_CATALOGUE_BASE_PYTHON)" -c 'import sys; assert sys.version_info[:3] == (3, 14, 4), "catalogue controls require CPython 3.14.4"'
	@$(UI_CATALOGUE_UV) --version | grep -E '^uv 0[.]11[.]17([[:space:]]|$$)' >/dev/null
	@test -s "$(UI_TESTS_DIR)/catalogue/requirements.lock.txt"
	@test ! -e "$(UI_CATALOGUE_PYTHON_DIR)" || { echo "select a fresh artifact environment; existing environments are preserved" >&2; exit 1; }
	@mkdir -p "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/cache" "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/build-scratch"
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_CATALOGUE_BASE_PYTHON)" -m venv --without-pip "$(UI_CATALOGUE_PYTHON_DIR)"
	@UV_CACHE_DIR="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/catalogue/cache" TMPDIR="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/catalogue/build-scratch" PYTHONDONTWRITEBYTECODE=1 $(UI_CATALOGUE_UV) pip sync --python "$(UI_CATALOGUE_PYTHON_DIR)/bin/python" --require-hashes --link-mode copy "$(UI_TESTS_DIR)/catalogue/requirements.lock.txt"

ui-test-install-catalogue-default: ## Install the unchanged default lock for its isolated entrypoint control
	@"$(UI_CATALOGUE_BASE_PYTHON)" -c 'import sys; assert sys.version_info[:3] == (3, 14, 4), "catalogue controls require CPython 3.14.4"'
	@$(UI_CATALOGUE_UV) --version | grep -E '^uv 0[.]11[.]17([[:space:]]|$$)' >/dev/null
	@test -s "$(UI_TESTS_DIR)/generated/requirements.lock.txt"
	@test ! -e "$(UI_TESTS_PYTHON_DIR)" || { echo "select a fresh artifact environment; existing environments are preserved" >&2; exit 1; }
	@mkdir -p "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/cache" "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/build-scratch"
	@PYTHONDONTWRITEBYTECODE=1 "$(UI_CATALOGUE_BASE_PYTHON)" -m venv --without-pip "$(UI_TESTS_PYTHON_DIR)"
	@UV_CACHE_DIR="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/catalogue/cache" TMPDIR="$(abspath $(BIJUX_DOCS_ARTIFACTS_DIR))/catalogue/build-scratch" PYTHONDONTWRITEBYTECODE=1 $(UI_CATALOGUE_UV) pip sync --python "$(UI_TESTS_PYTHON_DIR)/bin/python" --link-mode copy "$(UI_TESTS_DIR)/generated/requirements.lock.txt"

ui-test-catalogue: ## Execute all catalogue controls or one exact bounded group
	@set -eu; \
	groups="$(UI_CATALOGUE_GROUP)"; \
	if [ "$$groups" = all ]; then groups="source renderer typed-entrypoint tracked-entrypoint"; fi; \
	for group in $$groups; do \
	  BIJUX_CATALOGUE_DEFAULT_PYTHON="$(abspath $(UI_TESTS_PYTHON_DIR))/bin/python" PYTHONDONTWRITEBYTECODE=1 python3 "$(UI_TESTS_DIR)/catalogue/execution.py" run --python "$(UI_CATALOGUE_PYTHON_DIR)/bin/python" --group "$$group" --output "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/reports/$$group"; \
	  PYTHONDONTWRITEBYTECODE=1 "$(UI_CATALOGUE_PYTHON_DIR)/bin/python" "$(UI_TESTS_DIR)/catalogue/execution.py" verify --group "$$group" --output "$(BIJUX_DOCS_ARTIFACTS_DIR)/catalogue/reports/$$group"; \
	done
