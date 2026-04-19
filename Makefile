.PHONY: init start dev shutdown validate tests coverage

validate:
	@echo "\nRunning pre-commit validations on all files..."
	@pre-commit run --all-files

tests:
	@echo "\nRunning tests..."
	@uv run pytest -vv --cache-clear --color=yes --no-header --maxfail=1 --failed-first

coverage:
	@echo "\nGenerating test coverage..."
	@uv run coverage run -m pytest --no-summary --quiet
	@uv run coverage html