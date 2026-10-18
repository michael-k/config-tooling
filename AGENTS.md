# Agent Instructions

This document contains instructions for AI agents working on this project.

## Project Documentation

All project specifications live under [specs/](specs/). Start at
[specs/README.md](specs/README.md), the spec tree's entry point, and read
[specs/project/security-invariants.md](specs/project/security-invariants.md)
for the invariants every spec obeys.

`specs/` is the authoritative source of truth for this project: a mismatch
between a spec and the implementation is a bug in the implementation, not in
the spec.

The change process runs one way: edit the spec first, get it reviewed, then
bring the implementation to match. Never change behaviour and its spec in
opposite directions, and never adjust a spec to match code that has drifted
without saying so.

Do not explain a decision in a comment when a requirement already states
it. Cite the requirement ID instead.

`make spec-check` is the gate. Run it before committing.

## Command Execution Rules

### CRITICAL: Always Prefer `make` Targets

This project uses `uv` for Python dependency management and virtual environment isolation. All Python-related commands MUST be executed through the provided `make` targets when available, or through `uv run` as a fallback.

### Correct Command Patterns (in order of preference)

**1. Make targets (ALWAYS USE WHEN AVAILABLE):**
```bash
make test              # Run all tests
make test-unit         # Run unit tests
make test-integration  # Run integration tests (needs Incus)
make lint              # Run all linters
make python-lint       # Check Python code with ruff
make python-lint-fix   # Fix Python code issues with ruff
make python-typecheck  # Type-check Python code with ty
make spec-check        # Check spec traceability and regenerate the index
make clean             # Clean up generated files
```

**2. uv run (ONLY when no make target exists):**
```bash
uv run python -c "print('hello')"
uv run python -m incus --help
```

### Incorrect Command Patterns (NEVER USE)

```bash
# WRONG - bypasses uv environment
python -c "print('hello')"
pytest tests/

# WRONG - direct virtual environment activation
source .venv/bin/activate

# WRONG - using uv run when make target exists
uv run pytest tests/           # Use: make test
uv run ruff check tests/       # Use: make python-lint
```

## Why This Matters

1. **Consistency**: Make targets provide a consistent interface across all environments
2. **Simplicity**: Shorter commands that are easier to remember and type
3. **Dependency Isolation**: `uv` ensures all dependencies are installed and isolated
4. **Reproducibility**: Commands use the exact versions specified in `pyproject.toml`
5. **No Manual Setup**: `uv run` automatically creates and manages the virtual environment

## Common Command Translations

| Don't Use | Use Instead |
|-----------|-------------|
| `pytest` | `make test` |
| `pytest tests/unit/` | `make test-unit` |
| `ruff check` | `make python-lint` |
| `ty check` | `make python-typecheck` |
| `pip install` | `uv add` |

## Exception: System Commands

Pure system commands that don't involve Python or project dependencies can be run directly:

```bash
git status
git commit -m "message"
ls -la
cat file.txt
```

## Summary

**Golden Rules**:
1. **ALWAYS prefer `make` targets when they exist**
2. **NEVER use `pytest` or `ruff` directly** — always use `make test*` and `make python-lint*`
3. If no `make` target exists, use `uv run`
4. Never bypass the environment with direct `python`, `pytest`, `ruff` or `ty` commands
