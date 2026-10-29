# Editorial brief: mountainash-files

Status: confirmed — 2026-10-29 by the package owner, in the interactive `/ibook` creation session.
Source revision: `0ee86bccab95a29bf7521fbc5f35b85e3ab04db1` (`develop`, merge of PR #37), checked out on `docs/package-profile`. `src/` is clean; the only untracked files are the documentation workspace (`docs-site/`).
Profile basis: `docs-site/profile/manifest.json`, a full initial profile at that revision with 25 modules profiled and 1 ignored (`specs/__init__.py`). Facets: `users`, `maintainers`, `backend-architecture`, `broader-hype`. Gaps are listed in `docs-site/profile/coverage.md`.

## Purpose and reader outcomes

mountainash-files lets Python code read and write structured files through one API: CSV, TSV, JSON/NDJSON, Parquet, Excel (read-only) and XML, stored locally or anywhere mountainash-transport can reach. This book is the package's documentation. After reading it:

- A **user** can describe a file with `FileSourceSpec`/`FileSinkSpec`, call `parse`, `write`, `copy`, `stream`, `inspect_schema` and their in-memory equivalents, tune each format's options, select files with templates, globs and ZIP archives, and work with remote storage, named profiles and compression or encryption transforms. They can also interpret every error the package raises.
- A **maintainer** can explain the package's invariants and find where to change behaviour safely:
  - formats resolve before any I/O;
  - all storage access goes through the transport package root, enforced by ruff;
  - importing the package does not load heavy libraries;
  - one output seam normalises tabular data;
  - append is schema-checked;
  - archives and workbooks are bounded by decompression limits.
- An **extension author or architect** can add a format with `register_format` or an entry-point plugin, and can explain how the registry, access modes and engines fit together.

## Audience coverage

All four facets are included. Facets do not map to chapters; they set how deep each topic goes.

- **users** (essential): sets the main reading path. Its eight facet concepts (file specs; parse, write, copy and stream; in-memory buffers; format options; schema discovery; file selection; errors; custom formats) form the core chapters.
- **maintainers** (included): adds internals sections. These come at the end of the relevant chapter or in a closing internals chapter, covering the read pipeline and access routing, the registry bootstrap, the storage boundary, engine type normalisation, the CSV fast path versus the lexer, and decompression safety. Packaging and release invariants (lazy imports, version source) are covered briefly. Release process stays in `RELEASE.md`.
- **backend-architecture** (included): adds the format contract, resolution precedence, access modes, the engine for each format, plugin discovery and transport delegation. It shares explanations with the maintainer sections instead of repeating them, and anchors a per-format support matrix, which `coverage.md` lists as missing.
- **broader-hype** (included, but restrained): an evidence-backed opening page covering one API for many formats and locations, column-projected remote Parquet reads, and schema discovery without loading rows. It makes no claims beyond tested behaviour and does not mention publication status or a release date.

## Scope and exclusions

In scope:

- **Public API:** all 29 names exported from the package root.
- **Formats:** all built-in formats, with the honest limits of each:
  - XLSX has no writer;
  - only Parquet supports append;
  - XML is non-tabular;
  - `CsvSpec.dtypes` recognises six type names.
- **Storage:** what files passes to transport, namely storage and auth profiles, the location policy and transform pipelines.
- **Extras:** the optional extras and the `MissingDependencyError` raised when one is missing.

Out of scope or linked only:

- **Transport and settings internals:** backends, connection management and secret stores are linked to the mountainash-transport and mountainash-settings books, not explained here.
- **Planned work:** backlog items, roadmap and any planned format adapters (SAS, AEMO MMS).
- **Release and publishing process:** covered in `RELEASE.md`.
- **Process-history wording:** migration guidance in `docs/migration-reader-engines.md` is reused only for current-behaviour facts.

Prerequisites: Python 3.12 and basic familiarity with Arrow tables. Readers get one sentence on what a `pyarrow.Table` is and a link out; no prior knowledge of mountainash-transport is assumed.

## Depth and reading paths

The book progresses from concepts, to using the package, to internals:

1. **Concepts:** specs describe files, operations act on them, and formats are registered.
2. **Use:** a task-oriented chapter for each area, each backed by a runnable example.
3. **Internals:** architecture and extension.

Users can stop after part 2. Maintainers and architects can start at the concepts and jump straight to the internals. Shared explanations, such as format resolution and access modes, are written once and linked from elsewhere. The chapter structure itself will be proposed at the chapter-plan gate.

## Register

Package documentation: self-describing pages with no course preamble, learning objectives or recap sections.

## Reuse

Verify each of these against the source revision and reuse it selectively:

- the ten `examples/*/example.py` recipes, which are self-checking and run offline; use them as the code in the use chapters;
- `README.md` (capability table, extras table);
- `docs/advanced-usage.md` (operations, schema discovery, write modes, globs and archives, compression and storage, custom formats);
- `docs/profiles.md` (named profiles, secret references);
- current-behaviour facts from `docs/migration-reader-engines.md`.

No earlier book exists, so there is no course structure to inherit.

## Appendices

FAQ: included (confirmed 2026-10-29).
Glossary: included (confirmed 2026-10-29).
Both link to relevant chapter/section explanations.

## Visual policy

Mermaid first: read-path flow, format resolution precedence, access-mode routing and the transport boundary. MicroSims only when interaction adds explanatory value; none are proposed.
No quizzes in the Mountainash workflow.

## Approval and open questions

Confirmed on 2026-10-29: the whole brief as drafted, with these decisions.

- **Title:** "mountainash-files".
- **Internals placement:** internals for maintainers and architects go in a **separate final part**. The use chapters stay task-focused and link to it, and users can stop before it.
- **Limitations:** the profile's open behaviour questions are **documented as current behaviour, inside the chapters**. Each gives the exact behaviour and the workaround, with no promised fixes and no separate limitations page. Refresh updates the text when the backlog changes the behaviour.
- **Positioning:** `broader-hype` becomes **one evidence-only "Why mountainash-files" page**, three capabilities each backed by a test or example, with no release or publication claims.
- **Appendices:** FAQ and glossary are included, linked to chapter sections.
- **Visuals:** Mermaid first, no MicroSims proposed, no quizzes.

Open: none. The chapter structure is proposed at the chapter-plan gate.
