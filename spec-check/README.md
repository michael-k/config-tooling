# spec-check

The spec traceability checker behind every repository's `make spec-check`.
It reads the `specs/` tree of the repository it runs in and holds it to the
code: every requirement is cited, every citation names a live requirement,
every spec has its sections, the allowance register pairs up with its
claims, and every design's implementation map says what the code says. The
rules themselves are the `SPEC` spec in this repository's
`specs/spec-check/`; this file is how to use the command.

## Adopting it

1. Add this repository as a submodule at `config-tooling/`:

   ```sh
   git submodule add <url-of-config-tooling> config-tooling
   ```

2. Install the package from the submodule, in your `pyproject.toml`:

   ```toml
   [dependency-groups]
   dev = ["spec-check"]

   [tool.uv.sources]
   spec-check = { path = "config-tooling/spec-check", editable = true }
   ```

3. Say which files carry citations, also in `pyproject.toml`. There is no
   default: without the table, or with an empty list, the command exits
   with 2 (SPEC-15).

   ```toml
   [tool.spec-check]
   scan = [
       "Makefile",
       "README.md",
       "roles/**/*.yml",
       "tests/**/*.py",
   ]
   ```

   Globs are relative to the repository root. Files inside any submodule
   listed in `.gitmodules`, including `config-tooling/` itself, are never
   read, whatever the globs match (SPEC-14).

4. Add the make target:

   ```make
   spec-check:
   	uv run spec-check $(ARGS)
   ```

Run it from the repository root: the root is the current directory.

## What counts

- A citation is a `PREFIX-N` token whose prefix is in the registry table of
  `specs/README.md` (SPEC-1). Tokens with other prefixes are ignored.
- A citation in a Markdown file (`.md`) shows in the index but does not
  make a requirement cited, and a Markdown file gets no map row (SPEC-2,
  SPEC-12, SPEC-13).
- Each implementation map row for a scanned file lists exactly the IDs of
  that spec's prefixes the file cites, one by one, never as a range
  (SPEC-11, SPEC-13). Rows for paths the scan does not read, such as
  `pyproject.toml`, are checked only for existence (SPEC-10).

## Running it

```sh
make spec-check                                       # check, then rewrite specs/_traceability.md
make spec-check ARGS="--check"                        # check, write nothing, fail on a stale index
make spec-check ARGS="--spec project --spec testing"   # check only these specs
uv run python -m spec_check --check                   # the same entry point
```

- Without flags, the index `specs/_traceability.md` is rewritten after a
  run that found nothing, and no other file is touched (SPEC-18).
- `--check` writes nothing and reports an index that differs from the one a
  clean run would write. Use it in CI and pre-commit hooks (SPEC-19).
- `--spec NAME` (repeatable) limits the checks, and a `--check` comparison
  of the index, to the named spec directories. The allowance pairing is
  still judged over the whole tree, and a scoped run never writes the index
  (SPEC-20).

Every run prints the pending requirements of the specs it checked
(SPEC-17).

## Exit status

| Status | Meaning |
|---|---|
| `0` | No findings. |
| `1` | At least one finding; each is printed as `[kind] message`. |
| `2` | It could not run as asked: no `specs/README.md`, a missing or empty `[tool.spec-check]` `scan`, or a `--spec` naming no registered spec (SPEC-21). |
