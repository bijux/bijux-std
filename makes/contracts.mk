CONTRACT_ARTIFACT_ROOT ?= artifacts/contracts
CONTRACT_TMPDIR ?= $(CONTRACT_ARTIFACT_ROOT)/process
CONTRACT_PYCACHE_DIR ?= $(CONTRACT_ARTIFACT_ROOT)/pycache

.PHONY: contract-tests
contract-tests: ## Run shared-library unit and shell contract tests
	@command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
	@command -v shellcheck >/dev/null 2>&1 || { echo "shellcheck is required" >&2; exit 1; }
	@mkdir -p "$(CONTRACT_TMPDIR)" "$(CONTRACT_PYCACHE_DIR)"
	@TMPDIR="$(abspath $(CONTRACT_TMPDIR))" \
		PYTHONPYCACHEPREFIX="$(abspath $(CONTRACT_PYCACHE_DIR))" \
		python3 -m unittest discover -s tests -p 'test_*.py' -v
	@shellcheck \
		shared/bijux-makes/scripts/*.sh \
		shared/bijux-makes-rs/scripts/*.sh
	@shellcheck --severity=warning \
		shared/bijux-checks/check-bijux-std.sh \
		shared/bijux-checks/update-bijux-std.sh \
		shared/bijux-checks/scripts/resolve-shared-directories.sh \
		shared/bijux-docs/tooling/scripts/verify_bijux_docs_source_of_truth.sh
