.PHONY: changelog-validate changelog-check changelog-render
changelog-validate: ## Validate all final PR change records offline
	@python3 -B .github/scripts/changelog.py validate

changelog-check: changelog-validate ## Verify the central PR history projection
	@python3 -B .github/scripts/changelog.py render --check

changelog-render: changelog-validate ## Regenerate the central PR history after reconciling fragments
	@python3 -B .github/scripts/changelog.py render --write
