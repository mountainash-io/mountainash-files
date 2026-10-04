# File recipes

Focused, independently runnable examples of parsing, format options, writing,
file selection and storage profiles. Each recipe uses the same small sales
dataset so you can compare approaches; none imports another recipe.

## Setup

Use Python 3.12+ and follow the [development installation](../README.md#installation).
All recipes use core dependencies, run offline and require no credentials.
Run commands from the repository root. Configuration paths are relative to
the script, so an absolute script path also works from another working directory.

Each script prints a small result and checks it with assertions. Run without
Python's `-O` flag. File recipes use temporary directories that they remove.
The named-profile recipe temporarily selects its own configuration and restores
the previous environment value afterwards.

## Shared example data

The examples store a small sales report, `sales.csv`:

```text
region,total
north,120
south,95
```

Recipes embed or generate their own inputs. The format-options example expresses
the same report with semicolons; append and glob examples split it into two rows.

## Parsing

| Recipe | Question |
|---|---|
| [Local files](local_files/) | How do I write a table and read Arrow or Python records? |
| [In-memory data](in_memory/) | How do I parse and serialise buffers without a file? |
| [Format options](format_options/) | How do I override a suffix and configure CSV parsing? |

## Writing

| Recipe | Question |
|---|---|
| [Format conversion](format_conversion/) | How do I turn CSV into Parquet and NDJSON? |
| [Parquet append](parquet_append/) | How do I append rows and handle incompatible schemas? |

## Selecting files

| Recipe | Question |
|---|---|
| [Globs and templates](globs_and_templates/) | How do I select multiple files and skip missing inputs? |
| [ZIP archives](zip_archives/) | How do I parse selected members of an archive? |

## Storage and transforms

| Recipe | Question |
|---|---|
| [Gzip pipeline](gzip_pipeline/) | How do I compress writes and infer decompression on read? |
| [Byte operations](byte_operations/) | How do I copy and read bytes without parsing? |
| [Named profiles](named_profiles/) | How do I select storage from configuration? |

## Beyond these recipes

XLSX reads need `[xlsx]`; XML uses the standard library or optional lxml.
Remote S3, SFTP and authenticated HTTP operations need a live service and suitable
profiles. GPG needs GnuPG and keys. See the [support tables](../README.md#supported-formats-and-storage),
[format reference](../docs/advanced-usage.md#format-options) and
[profile guide](../docs/profiles.md).

## Verification

After installation, run every recipe from the repository root:

```bash
for recipe in examples/*/example.py; do
  python "$recipe" || exit 1
done
```

Each script asserts the result it demonstrates. Compare stdout with the
**Expected output** block in that recipe's README. Run the root README's
quick start separately. When adding a recipe, update this index, declare any
extra requirements and document deterministic output.
