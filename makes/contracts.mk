CONTRACT_ARTIFACT_ROOT ?= artifacts/contracts
CONTRACT_TMPDIR ?= $(CONTRACT_ARTIFACT_ROOT)/process
CONTRACT_PYCACHE_DIR ?= $(CONTRACT_ARTIFACT_ROOT)/pycache
CONTRACT_UNIT_PARTITION ?=
CONTRACT_UNIT_PARTITION_COUNT ?= 6
CONTRACT_UNIT_FLAGS ?=

include shared/bijux-docs/tooling/diagrams/Makefile

.PHONY: shared-contracts contract-unit-tests contract-tests
shared-contracts: ## Validate managed shared shell, Python, and JSON contracts
	@BIJUX_CONTRACT_ARTIFACTS_DIR="$(abspath $(CONTRACT_ARTIFACT_ROOT))/shared" \
		bash shared/bijux-checks/scripts/validate-shared-contracts.sh

contract-unit-tests: diagrams-install ## Run bijux-std unit contracts with the admitted diagram graph
	@command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
	@mkdir -p "$(CONTRACT_TMPDIR)" "$(CONTRACT_PYCACHE_DIR)"
ifneq ($(strip $(CONTRACT_UNIT_PARTITION)),)
	@test -z "$(CONTRACT_UNIT_FLAGS)" || { echo "Partitioned contracts do not accept unit filters" >&2; exit 1; }
	@TMPDIR="$(abspath $(CONTRACT_TMPDIR))" \
		PYTHONPYCACHEPREFIX="$(abspath $(CONTRACT_PYCACHE_DIR))" \
		BIJUX_DIAGRAM_DEPENDENCIES="$(abspath $(DIAGRAM_DEPENDENCIES))" \
		python3 shared/bijux-gitlab/contracts.py run \
			--partition-index "$(CONTRACT_UNIT_PARTITION)" \
			--partition-count "$(CONTRACT_UNIT_PARTITION_COUNT)" \
			--output "$(CONTRACT_ARTIFACT_ROOT)/unit-results.json"
else
	@TMPDIR="$(abspath $(CONTRACT_TMPDIR))" \
		PYTHONPYCACHEPREFIX="$(abspath $(CONTRACT_PYCACHE_DIR))" \
		BIJUX_DIAGRAM_DEPENDENCIES="$(abspath $(DIAGRAM_DEPENDENCIES))" \
		python3 -m unittest discover -s tests -p 'test_*.py' -v $(CONTRACT_UNIT_FLAGS)
endif

contract-tests: shared-contracts contract-unit-tests docs-theme-tests ## Run complete bijux-std contracts
