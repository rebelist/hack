.PHONY: check tests coverage

check:
	@echo "\nRunning pre-commit validations on all files..."
	@pre-commit run --all-files

tests:
	@echo "\nRunning tests..."
	@uv run pytest -v --cache-clear --failed-first --maxfail=1

coverage:
	@echo "\nGenerating test coverage..."
	@uv run coverage run -m pytest --no-summary --quiet
	@uv run coverage html