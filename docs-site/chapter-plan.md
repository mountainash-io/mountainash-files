# Chapter plan: mountainash-files

Status: approved — 2026-10-29 by the package owner, in the interactive `/ibook` creation session. Approved scope: the 11 chapters, their sections, the concept placement, `index.md`, `why.md` and the FAQ and glossary appendices, as listed below. Decided in the same session: chapter 4 stays one chapter, and the graph's 52.5% terminal-node ratio is accepted.

Implements: `docs-site/editorial-brief.md` (confirmed 2026-10-29).
Source: `0ee86bccab95a29bf7521fbc5f35b85e3ab04db1`. Profile: `docs-site/profile/manifest.json` (full, 25 modules, 4 facets). Graph: `docs-site/learning-graph/learning-graph.json` (120 concepts, 195 edges, valid DAG).

Placement check (automated against the graph): every concept has exactly one primary section, and every prerequisite is placed earlier in the same chapter or an earlier chapter.

## Structure

The book progresses from concepts (chapter 1), to using the package (chapters 2–8), to internals and extension (chapters 9–11), as the brief requires. Users can stop after chapter 8. Maintainers and architects can read chapter 1, then jump to chapter 9. Shared explanations (format resolution, access modes, profiles) are written once and linked.

Outside the chapters:

- `index.md`: landing page with install, a quick start and links into each part.
- `why.md` — **Why mountainash-files**: the evidence-only positioning page from the brief. It covers three capabilities: one API for six formats in local or remote storage (`examples/format_conversion`); reading only the projected columns of a remote Parquet file (`tests/test_access_routing.py`, chapter 4 › Parquet); and schema without rows (chapter 6). It makes no release claims.
- Appendices: `faq.md` and `glossary.md` (confirmed). Every entry links to the section that explains it.

| # | Slug | Title | Part | Audiences |
|---|---|---|---|---|
| 1 | `files-specs-and-formats` | Files, specs and formats | Concepts | users, maintainers, backend-architecture |
| 2 | `reading-and-writing` | Reading and writing files | Using the package | users, broader-hype |
| 3 | `selecting-files` | Selecting files | Using the package | users, maintainers |
| 4 | `format-options` | Format options | Using the package | users, backend-architecture |
| 5 | `storage-and-transforms` | Storage, profiles and transforms | Using the package | users, backend-architecture |
| 6 | `schema-discovery` | Schema discovery | Using the package | users, broader-hype |
| 7 | `write-modes` | Write modes and Parquet append | Using the package | users |
| 8 | `errors` | Errors and troubleshooting | Using the package | users, maintainers |
| 9 | `custom-formats` | Custom formats and plugins | Internals and extension | users, backend-architecture, maintainers |
| 10 | `architecture` | How mountainash-files works | Internals and extension | maintainers, backend-architecture |
| 11 | `format-internals` | Format engines and hardening | Internals and extension | maintainers, backend-architecture |

## Facet coverage

- **users**: the main path, chapters 1–8. The facet's eight concepts are covered: file specs (1), operations (2), in-memory buffers (2, 6), format options (4), schema discovery (6), file selection (3), errors (8) and custom formats (9).
- **maintainers**: chapter 1, then chapters 9–11. Read-pipeline routing (10), registry and bootstrap (9, 10), storage boundary (10), engine normalisation and the CSV fast path versus the lexer (11), decompression safety (3 for use, 11 for internals), packaging invariants (10). The release process stays in `RELEASE.md` (brief exclusion).
- **backend-architecture**: the format contract and plugins (9), resolution precedence (1), access modes (5 for use, 10 for routing), engines per format (4 support matrix, 11), transport delegation (5, 10).
- **broader-hype**: the `why.md` page only. Each of its three claims links to its proof section.

## Chapters

### 1. Files, specs and formats (`files-specs-and-formats`)

The model the whole package rests on: a file spec says where a file is and how to read it; a format key and its FormatSpec say how its bytes are interpreted; formats resolve from an explicit key, a media type or the path suffix.

- **Part:** Concepts. **Audiences:** users, maintainers, backend-architecture.
- **Prerequisite chapters:** none.
- **Why this is a chapter:** Concepts every later chapter assumes; kept in one chapter so the use chapters can start with tasks.
- **Sources:** src/mountainash_files/specs/; src/mountainash_files/formats/_types.py; src/mountainash_files/formats/_registry.py (resolve_format).
- **Reuse after verification:** README.md intro and capability table; docs/advanced-usage.md › File specs and format selection.
- **Visuals:** Mermaid: FileSpec → FileSourceSpec / FileSinkSpec class diagram; Mermaid: format resolution precedence flowchart.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Structured files, Arrow tables and records | Structured File (1 · 509); Arrow Table (2 · 51); Python Records (3 · 19); Tabular vs Non-Tabular Data (4 · 16) |
| Where files live | Storage Location (5 · 161); mountainash-transport (7 · 25); Optional Extras (6 · 15) |
| File specs | FileSpec (8 · 79); FileSourceSpec (9 · 44); FileSinkSpec (10 · 22); Immutable Specs (12 · 1) |
| Formats and format specs | Format Key (13 · 268); FormatSpec (14 · 103); Spec Format Field (11 · 1) |
| How a format is chosen | Suffix Detection (15 · 56); Media Type Detection (16 · 52); Transform Suffixes Skipped (18 · 2); Format Resolution Precedence (17 · 51) |

### 2. Reading and writing files (`reading-and-writing`)

The operations: parse a file into Arrow or records, write data in a format, convert between formats, copy bytes, open a raw stream, and do the same with in-memory buffers.

- **Part:** Using the package. **Audiences:** users, broader-hype.
- **Prerequisite chapters:** 1.
- **Why this is a chapter:** The task-entry chapter: the smallest complete read/write path before options or selection.
- **Sources:** src/mountainash_files/_operations.py; src/mountainash_files/formats/_types.py (ParseResult).
- **Reuse after verification:** examples/local_files; examples/format_conversion; examples/in_memory; examples/byte_operations; docs/advanced-usage.md › Operations and results.
- **Visuals:** Mermaid: operation map (spec in → operation → result out).

| Section | Primary concepts (ID · CIS) |
|---|---|
| Parsing a file | ParseResult (23 · 17); parse (22 · 15) |
| Arrow or Python records | Output Mode (arrow vs pydata) (24 · 2) |
| Writing and converting | write (26 · 14); Format Conversion (87 · 1) |
| Buffers you already hold | parse_bytes (25 · 2); serialise_bytes (27 · 1) |
| Copying bytes and opening streams | copy (28 · 1); stream (29 · 5) |

### 3. Selecting files (`selecting-files`)

Reading many files at once: path templates, globs and their matching rules, missing files, and ZIP or gzip archives with member selection and decompression limits.

- **Part:** Using the package. **Audiences:** users, maintainers.
- **Prerequisite chapters:** 1, 2.
- **Why this is a chapter:** Selection is orthogonal to format: it decides which bytes reach a parser. Separate from storage because it applies to local files too.
- **Sources:** src/mountainash_files/_operations.py (_read_source); src/mountainash_files/_glob.py; src/mountainash_files/specs/archive.py; src/mountainash_files/_archives.py.
- **Reuse after verification:** examples/globs_and_templates; examples/zip_archives; docs/advanced-usage.md › Globs, archives and missing files.
- **Visuals:** Mermaid: one source spec expanding into many ParseResults.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Path templates | Path Templates (30 · 1) |
| Globs | Glob Patterns (31 · 4); Glob Segment Semantics (32 · 1) |
| Missing files | Missing Files (on_missing) (33 · 1) |
| ZIP archives | ZipArchive (34 · 11); ZIP Member Selection (35 · 1); Unrecognised Archive Members (36 · 2); Skipped Members in Results (39 · 1) |
| Gzip archives and decompression limits | GzipCompression (37 · 6); Decompression Limits (38 · 5) |

### 4. Format options (`format-options`)

Every built-in format's options and limits: CSV and TSV dialects, headers and types; JSON and NDJSON shapes; Parquet projection; Excel sheets and limits; XML XPath; temporal inference; and a support matrix of what each format can do.

- **Part:** Using the package. **Audiences:** users, backend-architecture.
- **Prerequisite chapters:** 1, 2, 3.
- **Why this is a chapter:** One chapter with a section per format so the shared ideas (options round-trip, capability flags, temporal inference) are explained once. Current limits are stated in place: six dtype names; Excel read-only; no Parquet writer options.
- **Sources:** src/mountainash_files/formats/csv.py; tsv.py; json.py; parquet.py; xlsx.py; xml.py; _engines.py (infer_temporal).
- **Reuse after verification:** examples/format_options; docs/advanced-usage.md › Format options; docs/migration-reader-engines.md › Output types, Controlling inference, Remote Parquet (current-behaviour facts only).
- **Visuals:** Table (not Mermaid): format support matrix — parse / write / schema / append / access mode / extra.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Format specs as options | Format Options Round-Trip (20 · 1); Format Capability Flags (21 · 7) |
| Dates and times | Temporal Inference (58 · 1) |
| CSV | CsvSpec (51 · 15); Delimiter and Quoting Options (52 · 3); Null Sequence (53 · 1); Multi-Row Headers (54 · 1); Comment Rows (55 · 1); CSV Column Selection (56 · 1); CSV dtypes Overrides (57 · 1); Formula Neutralisation (59 · 1) |
| TSV | TsvSpec (60 · 2) |
| JSON and NDJSON | JsonSpec (61 · 6); Suffix Overrides (19 · 2); NDJSON (62 · 1); JSON Property Path (63 · 1); JSON Row Shapes (64 · 1) |
| Parquet | ParquetSpec (66 · 8); Parquet Column Projection (67 · 1) |
| Excel | XlsxSpec (68 · 8); Sheet Selection (69 · 1); Excel Is Read-Only (70 · 1); Workbook Container Limits (71 · 2); Inference Sample Rows (65 · 1) |
| XML | XmlSpec (72 · 4); XPath Selection (73 · 1); lxml and ElementTree Fallback (74 · 1) |
| What each format supports | Format Support Matrix (75 · 1) |

### 5. Storage, profiles and transforms (`storage-and-transforms`)

Reading and writing beyond local disk through mountainash-transport: storage and auth profiles, named profiles, location policy, compression and encryption transforms, suffix inference, stream access modes and remote URLs.

- **Part:** Using the package. **Audiences:** users, backend-architecture.
- **Prerequisite chapters:** 1, 2.
- **Why this is a chapter:** Everything files delegates to transport, gathered so users learn the spec fields once; transport internals are linked out, not explained.
- **Sources:** src/mountainash_files/specs/base.py; src/mountainash_files/specs/source.py; src/mountainash_files/_operations.py (_resolve_profiles, _read_bytes, stream).
- **Reuse after verification:** examples/named_profiles; examples/gzip_pipeline; examples/byte_operations; docs/profiles.md; docs/advanced-usage.md › Compression and storage.
- **Visuals:** Mermaid: spec → profile resolution → transport facade → backend.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Storage and auth profiles | Storage Profile (40 · 4); Auth Profile (42 · 1); Named Storage Profiles (41 · 1) |
| Location policy | Location Policy (43 · 1) |
| Remote sources | Remote URL Sources (50 · 1) |
| Compression and encryption transforms | Transform Pipeline (44 · 5); Transform Inference (infer) (45 · 1); Gzip Transform (46 · 1); GPG Encryption Transform (47 · 1) |
| Stream access | Stream Access Modes (48 · 4); Range Policy (49 · 1) |

### 6. Schema discovery (`schema-discovery`)

Observing the Arrow schema of each selected input without returning rows: full and bounded inference, the basis of each result, footer-only Parquet, and in-memory inspection.

- **Part:** Using the package. **Audiences:** users, broader-hype.
- **Prerequisite chapters:** 1, 2, 4.
- **Why this is a chapter:** A distinct operation with its own result type and cost model; follows format options because bounded inference depends on format behaviour.
- **Sources:** src/mountainash_files/_operations.py (inspect_schema, inspect_schema_bytes); csv/json/parquet/xlsx inspectors.
- **Reuse after verification:** docs/advanced-usage.md › Schema discovery.
- **Visuals:** Mermaid: basis decision (metadata / full / bounded).

| Section | Primary concepts (ID · CIS) |
|---|---|
| Inspecting a schema | SchemaResult (77 · 9); inspect_schema (76 · 5) |
| How a schema was obtained | Schema Basis (78 · 3); infer_schema_rows Budget (79 · 1) |
| Parquet footers | Footer-Only Parquet Schema (81 · 1) |
| In-memory buffers | inspect_schema_bytes (80 · 1) |

### 7. Write modes and Parquet append (`write-modes`)

Replace and append dispositions, raw byte writes, parent creation, and schema-checked Parquet append.

- **Part:** Using the package. **Audiences:** users.
- **Prerequisite chapters:** 1, 2, 4.
- **Why this is a chapter:** Kept apart from chapter 2 because append has its own rules and failure mode; short by design.
- **Sources:** src/mountainash_files/specs/sink.py; src/mountainash_files/_operations.py (write, _merge_append_tables).
- **Reuse after verification:** examples/parquet_append; docs/advanced-usage.md › Write modes.
- **Visuals:** none.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Replace and append | Write Disposition (83 · 5); create_path (86 · 1); Raw Bytes Write (88 · 1) |
| Appending to Parquet | Parquet Append (84 · 4); Append Schema Check (85 · 3) |

### 8. Errors and troubleshooting (`errors`)

Every error the package raises, what triggers it and how to fix it — including the archive errors that are not exported from the package root (current behaviour).

- **Part:** Using the package. **Audiences:** users, maintainers.
- **Prerequisite chapters:** 1, 2, 3, 6, 7.
- **Why this is a chapter:** A reference chapter users jump to from a traceback; each entry links back to the section that explains the cause.
- **Sources:** src/mountainash_files/formats/_exceptions.py; src/mountainash_files/_exceptions.py; src/mountainash_files/_archives.py.
- **Reuse after verification:** tests/test_exceptions.py messages as verified examples.
- **Visuals:** Mermaid: exception hierarchy class diagram.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Format errors | FormatError (89 · 5); UnknownFormatError (90 · 1); ParseError (91 · 1); SchemaDiscoveryUnsupportedError (82 · 1) |
| Write errors | WriteError (93 · 2); AppendSchemaMismatchError (94 · 1) |
| Missing optional dependencies | MissingDependencyError (95 · 1) |
| Archive errors | Archive Errors (96 · 1) |

### 9. Custom formats and plugins (`custom-formats`)

Adding a format: the parser, serialiser and schema-inspector protocols, register_format and its options, lazy references, entry-point plugins, override rules, access-mode registration and the treespec complex-handler linkage.

- **Part:** Internals and extension. **Audiences:** users, backend-architecture, maintainers.
- **Prerequisite chapters:** 1, 5, 6, 8.
- **Why this is a chapter:** Opens the internals part: the public extension surface, before the private machinery behind it.
- **Sources:** src/mountainash_files/formats/_registry.py; src/mountainash_files/formats/_protocols.py; src/mountainash_files/formats/_types.py.
- **Reuse after verification:** docs/advanced-usage.md › Custom formats; docs/migration-reader-engines.md › Plugin formats; 2026-07-05 arrow-output design §1.4 (COMPLEX_HANDLER_KEY, import-light plugins) — mountainash-central.
- **Visuals:** Mermaid: plugin discovery sequence.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Format protocols | FormatParser Protocol (98 · 1); FormatSerialiser Protocol (99 · 1); FormatSchemaInspector Protocol (100 · 1) |
| Registering a format | register_format (97 · 16); Registration Override (103 · 1); FormatConflictError (92 · 1); Access Mode Registration (104 · 2) |
| Lazy registration and plugins | Lazy Dotted-Path Registration (101 · 5); Entry-Point Plugins (102 · 4); Import-Light Plugin Modules (105 · 1) |
| Complex formats and treespec | COMPLEX_HANDLER_KEY Linkage (106 · 1) |

### 10. How mountainash-files works (`architecture`)

The read pipeline, access routing, the output-normalisation seam, registry internals and bootstrap, and the package invariants: storage only through transport, lazy imports, version source.

- **Part:** Internals and extension. **Audiences:** maintainers, backend-architecture.
- **Prerequisite chapters:** 1, 2, 3, 4, 5, 9.
- **Why this is a chapter:** Cross-cutting machinery maintainers change most; separate from format internals so this chapter stays format-agnostic.
- **Sources:** src/mountainash_files/_operations.py; src/mountainash_files/formats/__init__.py; src/mountainash_files/formats/_registry.py; pyproject.toml [tool.ruff.lint] banned-api; hatch.toml.
- **Reuse after verification:** tests/test_access_routing.py, tests/test_lazy_imports.py as evidence.
- **Visuals:** Mermaid: read pipeline flowchart; Mermaid: access routing decision; Mermaid: storage boundary.

| Section | Primary concepts (ID · CIS) |
|---|---|
| The read pipeline | Read Pipeline (107 · 2); Access Routing (108 · 1) |
| One output seam | Output Normalisation Seam (109 · 1) |
| Inside the registry | Format Registry Internals (110 · 2); Registration Bootstrap (111 · 1) |
| Package invariants | Storage Boundary Principle (112 · 1); Lazy Import Invariant (113 · 2); Package Version Source (120 · 1) |

### 11. Format engines and hardening (`format-internals`)

How built-in readers are implemented: engine type normalisation, the CSV native path versus the lexer and safe field encoding, the calamine Excel reader, append merge semantics, and ZIP container hardening.

- **Part:** Internals and extension. **Audiences:** maintainers, backend-architecture.
- **Prerequisite chapters:** 1, 2, 3, 4, 7.
- **Why this is a chapter:** Format-specific internals and security hardening; the deepest material, read only by people changing readers.
- **Sources:** src/mountainash_files/formats/_engines.py; _delimited.py; _rows.py; _xlsx_calamine.py; src/mountainash_files/_archives.py; _operations.py (_merge_append_tables).
- **Reuse after verification:** docs/migration-reader-engines.md (current-behaviour facts).
- **Visuals:** Mermaid: CSV path selection; Mermaid: zip container check sequence.

| Section | Primary concepts (ID · CIS) |
|---|---|
| Engine output types | Engine Type Normalisation (114 · 2) |
| CSV internals | CSV Native Path vs Lexer (115 · 2); Safe CSV Field Encoding (116 · 1) |
| Excel internals | XLSX Calamine Reader (119 · 1) |
| Append merge rules | Append Merge Semantics (118 · 1) |
| ZIP container hardening | ZIP Container Hardening (117 · 1) |

## Elaboration guidance (internal)

The book-wide maximum CIS is 509, for Structured File. Concepts with high CIS carry the most downstream understanding, so they get the fullest explanation and an example. Concepts with CIS 1 are leaf options: a definition, the default and one example line.

Highest CIS: Structured File (509), Format Key (268), Storage Location (161), FormatSpec (103), FileSpec (79), Suffix Detection (56), Media Type Detection (52), Arrow Table (51), Format Resolution Precedence (51), FileSourceSpec (44), mountainash-transport (25), FileSinkSpec (22).

## Visual policy

All diagrams use Mermaid, plus one comparison table (the support matrix). No MicroSims are proposed and there are no quizzes. The graph and planning artifacts stay internal and are not published.

## Open questions

- Resolved on 2026-10-29: the 52.5% terminal-node ratio is accepted, and leaf options stay separate concepts.
- Resolved on 2026-10-29: chapter 4 (28 concepts in 9 sections) stays one chapter.
