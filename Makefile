.PHONY: install build run dev demo reset-demo test seed

install:
	pip install -e ".[dev]"
	cd frontend && npm install

# Build the frontend so the API serves the whole app on one port.
build:
	cd frontend && npm run build

# Standalone app: http://localhost:8000
run: build
	uvicorn denialdesk.api.main:app --port 8000

# Hot-reload development: API on :8000, Vite on :5173 (proxies /api).
dev:
	@echo "Run in two terminals:  uvicorn denialdesk.api.main:app --reload   |   cd frontend && npm run dev"

demo: reset-demo

reset-demo:
	@bash scripts/reset_demo.sh

seed:
	@python scripts/seed_demo.py

test:
	python -m pytest tests/ -v --tb=short
