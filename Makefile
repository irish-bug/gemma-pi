# Project Artoo - Operational Makefile

.PHONY: setup test run commit clean

# Initial Setup
setup:
	@echo "Installing dependencies..."
	@/home/shane/google-labs/env/bin/pip install pyalsaaudio numpy
	@echo "Installing Git hooks..."
	@mkdir -p .git/hooks
	@cat <<EOF > .git/hooks/pre-commit
#!/bin/bash
echo " [CI/CD] Running Pre-Commit Unit Tests..."
source ~/google-labs/env/bin/activate
python3 /home/shane/google-labs/test_gemma.py
if [ \$? -ne 0 ]; then
    echo " [ERROR] Unit tests failed. Commit aborted."
    exit 1
fi
echo " [SUCCESS] Tests passed. Proceeding with commit."
EOF
	@chmod +x .git/hooks/pre-commit
	@echo "Setup complete. Environment is protected."

# Run Unit Tests
test:
	@echo "Running tests..."
	@/home/shane/google-labs/env/bin/python3 /home/shane/google-labs/test_gemma.py

# Run the Gemma Engine with Debug
run:
	@echo "Launching Gemma Voice Engine..."
	@/home/shane/google-labs/env/bin/python3 /home/shane/google-labs/gemma_speaks.py --debug

# Safe Commit (Runs tests first)
commit:
	@make test
	@git add .
	@read -p "Enter commit message: " msg; \
	git commit -m "$$msg"
	@git push
	@echo "Deployment to GitHub complete."

# Clean up temporary files
clean:
	@rm -rf __pycache__ .pytest_cache
	@echo "Workspace cleaned."
