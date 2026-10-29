# Chapters

1. [Files, specs and formats](./files-specs-and-formats/index.md): file specs, format specs and how a format is chosen for a path.
2. [Reading and writing files](./reading-and-writing/index.md): `parse`, `write`, `copy`, `stream` and their in-memory counterparts.
3. [Selecting files](./selecting-files/index.md): path templates, globs, missing files, and ZIP and gzip archives.
4. [Format options](./format-options/index.md): options and limits for CSV, TSV, JSON, Parquet, Excel and XML.
5. [Storage, profiles and transforms](./storage-and-transforms/index.md): remote storage, named profiles, location policy, compression and encryption.
6. [Schema discovery](./schema-discovery/index.md): reading a file's Arrow schema without loading its rows.
7. [Write modes and Parquet append](./write-modes/index.md): replacing files and appending to Parquet.
8. [Errors and troubleshooting](./errors/index.md): what each error means and how to fix it.
9. [Custom formats and plugins](./custom-formats/index.md): adding a format with `register_format` or an entry-point plugin.
10. [How mountainash-files works](./architecture/index.md): the read pipeline, the format registry and the package's invariants.
11. [Format engines and hardening](./format-internals/index.md): how the built-in readers work and how archives are bounded.
