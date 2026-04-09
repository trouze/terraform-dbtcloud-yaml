.DEFAULT_GOAL := help

.PHONY: fmt fmt-check lint validate test test-integration docs pre-commit pre-commit-all help

fmt: ## Auto-format all Terraform files
	terraform fmt -recursive

fmt-check: ## Check formatting without modifying (used in CI)
	terraform fmt -check -recursive

lint: ## Run tflint on all modules
	tflint --recursive

validate: ## Run terraform validate (requires terraform init)
	terraform init -backend=false -reconfigure
	terraform validate

test: ## Run terraform test with mock providers (no credentials needed)
	terraform test

test-integration: ## Run Go integration tests against a real dbt Cloud account (requires DBT_CLOUD_ACCOUNT_ID and DBT_CLOUD_TOKEN)
	cd test && RUN_INTEGRATION_TESTS=1 go test -v -timeout 30m -run Integration ./...

docs: ## Regenerate terraform-docs for root module and all submodules
	terraform-docs -c .terraform-docs.yml .
	@for dir in modules/*/; do \
		module=$$(basename $$dir); \
		terraform-docs markdown table \
			--output-file "../../docs/reference/module-$${module}.md" \
			--output-mode replace \
			"$$dir"; \
	done

pre-commit: ## Run all pre-commit hooks on staged files
	pre-commit run

pre-commit-all: ## Run all pre-commit hooks on all files
	pre-commit run --all-files

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
