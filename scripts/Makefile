# Infrastructure Makefile
# Common operations for managing the infrastructure

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Variables
CLUSTER ?=
APP ?=

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Cluster operations
.PHONY: new-cluster
new-cluster: ## Create a new cluster (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make new-cluster CLUSTER=<name>"; exit 1; fi
	./new-cluster.sh $(CLUSTER)

.PHONY: bootstrap-argocd
bootstrap-argocd: ## Bootstrap ArgoCD on a cluster (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make bootstrap-argocd CLUSTER=<name>"; exit 1; fi
	./bootstrap-argocd.sh $(CLUSTER)

# App operations
.PHONY: new-app
new-app: ## Create a new app (APP=name [CLUSTER=name])
	@if [ -z "$(APP)" ]; then echo "Usage: make new-app APP=<name> [CLUSTER=<name>]"; exit 1; fi
	./new-app.sh $(APP) $(CLUSTER)

# Terraform operations
.PHONY: tf-init-global
tf-init-global: ## Initialize global Terraform
	cd ../terraform/global && terraform init

.PHONY: tf-plan-global
tf-plan-global: ## Plan global Terraform
	cd ../terraform/global && terraform plan

.PHONY: tf-apply-global
tf-apply-global: ## Apply global Terraform
	cd ../terraform/global && terraform apply

.PHONY: tf-init-cluster
tf-init-cluster: ## Initialize cluster Terraform (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make tf-init-cluster CLUSTER=<name>"; exit 1; fi
	cd ../terraform/clusters/$(CLUSTER) && terraform init

.PHONY: tf-plan-cluster
tf-plan-cluster: ## Plan cluster Terraform (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make tf-plan-cluster CLUSTER=<name>"; exit 1; fi
	cd ../terraform/clusters/$(CLUSTER) && terraform plan

.PHONY: tf-apply-cluster
tf-apply-cluster: ## Apply cluster Terraform (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make tf-apply-cluster CLUSTER=<name>"; exit 1; fi
	cd ../terraform/clusters/$(CLUSTER) && terraform apply

# Helm operations
.PHONY: helm-update-app
helm-update-app: ## Update Helm dependencies for an app (APP=name)
	@if [ -z "$(APP)" ]; then echo "Usage: make helm-update-app APP=<name>"; exit 1; fi
	cd ../kubernetes/apps/$(APP) && helm dependency update

.PHONY: helm-update-argocd
helm-update-argocd: ## Update ArgoCD Helm dependencies (CLUSTER=name)
	@if [ -z "$(CLUSTER)" ]; then echo "Usage: make helm-update-argocd CLUSTER=<name>"; exit 1; fi
	cd ../kubernetes/clusters/$(CLUSTER)/argocd/bootstrap && helm dependency update

# Validation
.PHONY: validate
validate: ## Validate Terraform and Helm configurations
	@echo "Validating Terraform..."
	@cd ../terraform/global && terraform validate
	@for dir in ../terraform/clusters/*/; do \
		if [ -f "$$dir/main.tf" ] && [ "$$(basename $$dir)" != "_template" ]; then \
			echo "Validating $$dir"; \
			cd "$$dir" && terraform validate; \
			cd - > /dev/null; \
		fi \
	done
	@echo ""
	@echo "Validating Helm charts..."
	@for dir in ../kubernetes/apps/*/; do \
		if [ -f "$$dir/Chart.yaml" ] && [ "$$(basename $$dir)" != "_template" ]; then \
			echo "Validating $$dir"; \
			helm lint "$$dir" || true; \
		fi \
	done

.PHONY: fmt
fmt: ## Format Terraform files
	terraform fmt -recursive ../terraform/
