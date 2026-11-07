ifndef BIJUX_NODE_WORKSPACE_INCLUDED
BIJUX_NODE_WORKSPACE_INCLUDED := 1

NODE ?= node
NPM ?= npm
BIJUX_NODE_ARTIFACTS ?= $(CURDIR)/artifacts
export NPM_CONFIG_CACHE ?= $(BIJUX_NODE_ARTIFACTS)/cache/npm
export NPM_CONFIG_LOGS_DIR ?= $(BIJUX_NODE_ARTIFACTS)/logs/npm
export TMPDIR ?= $(BIJUX_NODE_ARTIFACTS)/work

.PHONY: node-environment node-install node-build node-test node-check
node-environment:
	@mkdir -p "$(TMPDIR)" "$(NPM_CONFIG_CACHE)" "$(NPM_CONFIG_LOGS_DIR)"
	@$(NODE) -e 'const p = require("./package.json"); if (Number(process.versions.node.split(".")[0]) < 22 || p.private !== true || !Array.isArray(p.workspaces) || !p.workspaces.length) { throw new Error("Expected Node >=22 and a private npm workspace root"); }'

node-install: node-environment ## Install the exact workspace lockfile
	@$(NPM) ci

node-build: node-environment ## Build public workspaces through their owning scripts
	@$(NPM) run build

node-test: node-environment ## Run meaningful package-owned workspace tests
	@$(NPM) test

node-check: node-environment ## Verify workspace metadata and public declarations
	@$(NPM) run check:workspace
	@$(NPM) run check:types

endif
