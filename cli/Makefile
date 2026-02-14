.PHONY: help build install test clean

BINARY_NAME=hrafngrima
BINARY_PATH=bin/$(BINARY_NAME)
INSTALL_PATH=$(HOME)/.local/bin

help:
	@echo "Hrafngrima CLI - Makefile targets"
	@echo ""
	@echo "  make build       - Build the CLI binary"
	@echo "  make install     - Build and install to ~/.local/bin"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Remove build artifacts"
	@echo "  make run-sync    - Build and run 'sync' command"
	@echo "  make run-health  - Build and run 'health' command"

build:
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p bin
	@go build -o $(BINARY_PATH) -v

install: build
	@echo "Installing to $(INSTALL_PATH)..."
	@mkdir -p $(INSTALL_PATH)
	@cp $(BINARY_PATH) $(INSTALL_PATH)/
	@chmod +x $(INSTALL_PATH)/$(BINARY_NAME)
	@echo "✓ Installed to $(INSTALL_PATH)/$(BINARY_NAME)"
	@echo "  Add to PATH: export PATH=\"$(INSTALL_PATH):\$$PATH\""

test:
	@echo "Running tests..."
	@go test -v ./...

clean:
	@echo "Cleaning..."
	@rm -rf bin/
	@go clean

run-sync: build
	@$(BINARY_PATH) sync

run-health: build
	@$(BINARY_PATH) health

run-contacts: build
	@$(BINARY_PATH) contacts list

run-analyze: build
	@$(BINARY_PATH) analyze --limit 10

# Development helpers
fmt:
	@go fmt ./...

lint:
	@golangci-lint run ./...

mod-tidy:
	@go mod tidy

mod-vendor:
	@go mod vendor

.PHONY: fmt lint mod-tidy mod-vendor
