---
title: Why mountainash-files
---

# Why mountainash-files

mountainash-files gives a Python program one way to work with structured files, whatever their format and wherever they are stored. Three capabilities set it apart from calling each format's library directly.

## One API for six formats and many storage locations

A `FileSourceSpec` names a file and, optionally, a storage profile. `parse` reads it as CSV, TSV, JSON, Parquet, Excel or XML, choosing the format from the path suffix or an explicit format. `write` produces CSV, TSV, JSON or Parquet from the same Arrow table. Converting CSV to Parquet takes one `parse` and one `write`, and the code does not change when the files move from local disk to a backend reached through mountainash-transport. The repository's `examples/format_conversion/example.py` runs this conversion, and [Reading and writing files](chapters/reading-and-writing/index.md#writing-and-converting) explains it.

## Only the columns you select are read from remote Parquet

When a `ParquetSpec` names a subset of columns, mountainash-files reads the file through a random-access handle. The Parquet reader then fetches the footer and the selected column chunks, not the whole object. Without a projection, or when a decompression or decryption transform applies, it reads the whole object. `tests/test_access_routing.py` checks this routing. See [Parquet](chapters/format-options/index.md#parquet) for the options and [How mountainash-files works](chapters/architecture/index.md#the-read-pipeline) for the routing.

## Schemas without loading data

`inspect_schema` reports the Arrow schema of each selected file and how it was obtained. For Parquet it reads only the footer metadata. For CSV and NDJSON a row budget limits how much of the file is parsed. Each result's `basis` (`metadata`, `full` or `bounded`) says which applied. See [Schema discovery](chapters/schema-discovery/index.md).
