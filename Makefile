.PHONY: demo reset-demo test seed

demo: reset-demo

reset-demo:
	@bash scripts/reset_demo.sh

seed:
	@python scripts/seed_demo.py

test:
	python -m pytest tests/ -v --tb=short
