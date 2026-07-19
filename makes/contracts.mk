CONTRACT_ARTIFACT_ROOT ?= artifacts/contracts
CONTRACT_TMPDIR ?= $(CONTRACT_ARTIFACT_ROOT)/process
CONTRACT_PYCACHE_DIR ?= $(CONTRACT_ARTIFACT_ROOT)/pycache

.PHONY: shared-contracts contract-unit-tests contract-tests
shared-contracts: ## Validate managed shared shell, Python, and JSON contracts
	@BIJUX_CONTRACT_ARTIFACTS_DIR="$(abspath $(CONTRACT_ARTIFACT_ROOT))/shared" \
		bash shared/bijux-checks/scripts/validate-shared-contracts.sh

contract-unit-tests: ## Run bijux-std unit contracts
	@command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
	@mkdir -p "$(CONTRACT_TMPDIR)" "$(CONTRACT_PYCACHE_DIR)"
	@TMPDIR="$(abspath $(CONTRACT_TMPDIR))" \
		PYTHONPYCACHEPREFIX="$(abspath $(CONTRACT_PYCACHE_DIR))" \
		python3 -m unittest discover -s tests -p 'test_*.py' -v

contract-tests: shared-contracts contract-unit-tests ## Run complete bijux-std contracts
