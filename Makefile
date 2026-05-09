# Project Artoo - Operational Makefile v16.3

.PHONY: setup test run commit clean

# Initial Setup
setup:
	@echo "Installing dependencies..."
	@/home/shane/google-labs/env/bin/pip install pyalsaaudio numpy
	@echo "Installing Git hooks..."
	@mkdir -p .git/hooks
	@printf '#!/bin/bash\necho " [CI/CD] Running Pre-Commit Unit Tests..."\nsource ~/google-labs/env/bin/activate\nmake test\nif [ $$? -ne 0 ]; then\n    echo " [ERROR] Unit tests failed. Commit aborted."\n    exit 1\nfi\necho " [SUCCESS] Tests passed. Proceeding with commit."\n' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Setup complete. Environment is protected."

# Run Unit Tests (VAD + Emotions)
test:
	@echo "Running VAD Latency Tests..."
	@/home/shane/google-labs/env/bin/python3 /home/shane/google-labs/test_gemma.py
	@echo "Running Emotion Engine Tests..."
	@/home/shane/google-labs/env/bin/python3 /home/shane/google-labs/test_emotions.py

# Run the Gemma Engine with Debug
run:
	@echo "Launching Gemma Voice Engine..."
	@PA_ALSA_PLUGHW=1 /home/shane/google-labs/env/bin/python3 /home/shane/google-labs/gemma_speaks.py --debug

# Safe Commit
commit:
	@make test
	@git add .
	@read -p "Enter commit message: " msg; \
	git commit -m "$$msg"
	@git push
	@echo "Deployment to GitHub complete."

# Clean up
clean:
	@rm -rf __pycache__ .pytest_cache
	@echo "Workspace cleaned."
