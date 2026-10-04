# Contributing

[README](README.md) · [Examples](examples/) · [Release process](RELEASE.md)

## Development setup

Use Python 3.12 or newer. Keep sibling checkouts next to this repository:
`mountainash-settings`, `mountainash-secrets`, `mountainash-auth-client`,
`mountainash-transport`, and `mountainash`. Hatch selects runtime sibling sources
through `requirements-hatch.txt` before installing files. See the
[README installation](README.md#installation) for a direct editable install.

Branch from `develop`; pull requests target `develop`. Run:

```sh
hatch run test:test
hatch run test:cov
hatch run ruff:check
hatch run mypy:check
```

CI checks out the four runtime siblings into `temp/` from the PR head branch
(or dispatched ref), falling back to the PR base branch (or `fallback_branch`).
The pytest workflow separately checks out test-only `mountainash`, then runs
`hatch run test_github:cov`. All tests under `tests/`, including cross-package
integration tests, run; sibling repositories' own suites are not collected.
Hatch owns local/CI source paths rather than a conflicting local-only uv override.
The `build_github` environment supplies the SBOM commands. Main-targeting PRs also
validate runtime dependencies and require a `release/*` or `hotfix/*` source branch.

## Tests and examples

`python -m pytest` runs the core suite with core dependencies and pytest,
pytest-mock, and packaging installed. Optional dependencies are path-selected:

```sh
# In a separate environment with mountainash-files[xlsx] installed:
python -m pytest tests_optional/xlsx
# In a separate environment with mountainash-files[xml] installed:
python -m pytest tests/test_xml.py tests_optional/xml
```

The XLSX fixture is tracked under `tests/fixtures`; core tests never generate it
or require an XLSX engine. Optional cohorts fail if their declared dependency is
missing rather than skipping unrelated tests. The
`tests_optional/mountainash/test_relation.py` cohort additionally needs a
compatible mountainash installation and belongs to subsequent consumer
qualification; it is excluded from the default suite. Existing Hatch sibling
source configuration is development convenience, not installed-artifact proof.

Run the [recipes](examples/#verification) and compare their output with the
individual READMEs when changing examples. Each recipe should demonstrate one
public API concept, run independently and clean up any files it creates.

## Type checking

Run `hatch run mypy:check` to check both `src/mountainash_files` and `tests`.
The dedicated environment installs pytest, packaging, and pinned third-party
stubs during provisioning; checking does not install packages or require pip.
To verify provisioning from scratch, run `hatch env remove mypy` first.

The PyArrow stubs currently require PyArrow 20 or newer in this development
environment; the package's runtime dependency floor remains unchanged.
Use typed settings, auth-client and transport artifacts (settings PR #84,
auth-client PR #36 and transport PR #100 or their descendants). Source and
tests are checked together, without import suppression.

Files ships a PEP 561 `py.typed` marker. Public operations, specs, exceptions
and result wrappers have inline annotations. `FormatSpec.from_options()`
retains the receiving subclass type. `ParseResult.data` deliberately remains
dynamic: registered plugins can return arbitrary payloads. JSON's format parser
returns `pyarrow.Table | list[object]`; narrow that union before using table
methods. These contracts do not imply that every plugin or optional SDK is
statically typed.

## Installed typing qualification

Build one wheel each for settings, auth-client and transport into a directory,
then run:

```sh
hatch run typing:qualify --dependency-wheels /path/to/dependency-wheels \
  --output /path/outside/the/checkout/new-evidence-directory
```

The `typing` Hatch environment uses Python 3.12. For Python 3.13, install
`build==1.4.0` and `packaging` in a Python 3.13 environment and invoke
`python tools/qualify_typing.py` with the same arguments. The Typing CI workflow
qualifies both versions. It uses the same dependency-checkout convention as
the existing test workflow; dependency wheels must contain their markers.

The qualifier builds a direct wheel and an sdist-rebuilt wheel, verifies
marker inclusion, and checks/runs a consumer in fresh environments outside
the source checkout. Expected-invalid calls must fail with the specified
diagnostics; missing errors fail qualification. Receipts retain artifact
hashes, exact installed origins, dependency versions and logs. The sdist
includes the qualification recipe and fixture. Local-wheel qualification
does not establish package publication or minimum-dependency compatibility.
