.PHONY: help test test-unit test-integration lint python-lint python-lint-fix python-typecheck spec-check clean

help:
	@echo "config-tooling - Available targets:"
	@echo "  test               Run all tests"
	@echo "  test-unit          Run unit tests only"
	@echo "  test-integration   Run integration tests only (needs Incus)"
	@echo "  lint               Run all linters (python-lint, python-typecheck, spec-check)"
	@echo "  python-lint        Check Python code with ruff"
	@echo "  python-lint-fix    Fix Python code issues with ruff"
	@echo "  python-typecheck   Type-check Python code with ty"
	@echo "  spec-check         Check spec traceability and rewrite specs/_traceability.md"
	@echo "  clean              Remove caches"

# PRJ-4, PRJ-5: every target runs its tool through uv.
# TEST-1: each tier is selected by marker over both packages' tests.
test:
	uv run pytest $(ARGS)

test-unit:
	uv run pytest -m unit $(ARGS)

test-integration:
	uv run pytest -m integration $(ARGS)

lint: python-lint python-typecheck spec-check

python-lint:
	uv run ruff check incus/ spec-check/ tests/

python-lint-fix:
	uv run ruff check --fix incus/ spec-check/ tests/

python-typecheck:
	uv run ty check

# PRJ-6: the checker from this working tree checks this tree.
spec-check:
	uv run spec-check $(ARGS)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
