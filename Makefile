# Project Artoo - Operational Makefile v18
# Status: Synchronized with gemma_stable_env & Gemma Live v18

SHELL := /bin/bash

.PHONY: setup test run commit clean

# Central Environment Configuration
ENV_DIR = /home/shane/google-labs/gemma_stable_env
PYTHON  = $(ENV_DIR)/bin/python3
PIP     = $(ENV_DIR)/bin/pip

# Initial Setup & Git Guard Rails
setup:
	@echo "Installing stable infrastructure dependencies..."
	@$(PIP) install pyalsaaudio numpy websockets sounddevice openwakeword spotipy google-genai requests
	@echo "Installing Git hooks..."
	@mkdir -p .git/hooks
	@printf '#!/bin/bash\necho " [CI/CD] Running Pre-Commit Verifications..."\nmake test\nif [ $$? -ne 0 ]; then\n    echo " [ERROR] Environment checks failed. Commit aborted."\n    exit 1\nfi\necho " [SUCCESS] System clean. Proceeding with commit."\n' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Setup complete. Core environment is secured."

# Verification Layer: syntax check + real unit test suite (test_*.py) on this
# repo's own code (previously py_compiled google-labs' copies by mistake --
# that never actually verified anything committed to this repo).
test:
	@echo "Verifying local code syntax baseline..."
	@$(PYTHON) -m py_compile gemma_runtime.py artoo_tools.py gemma_tools.py spotify_control.py
	@echo "Running unit test suite..."
	@$(PYTHON) -m unittest discover -s . -p "test_*.py" -v
	@echo " [SUCCESS] Core scripts are structurally sound and unit tests pass."

# Launch the Primary Live Voice Engine
run:
	@echo "Launching Gemma Live Bidirectional Voice Engine..."
	@PA_ALSA_PLUGHW=1 $(PYTHON) /home/shane/google-labs/gemma_runtime.py

# Safe Automated Cloud Deployment Chain
commit:
	@make test
	@git add .
	@bash -c 'read -p "Enter commit message: " msg; git commit -m "$$msg"'
	@echo "Pushing validated architecture to GitHub..."
	@git push
	@echo "Deployment to cloud repository complete."

# System Workspace Purge
clean:
	@rm -rf __pycache__ .pytest_cache
	@echo "Workspace cleaned."