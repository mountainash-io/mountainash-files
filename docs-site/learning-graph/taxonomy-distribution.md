# Taxonomy Distribution Report

## Overview

- **Total Concepts**: 120
- **Number of Taxonomies**: 13
- **Average Concepts per Taxonomy**: 9.2

## Distribution Summary

| Category | TaxonomyID | Count | Percentage | Status |
|----------|-----------|-------|------------|--------|
| JSON, Parquet, Excel and XML | FMTS | 15 | 12.5% | ✅ |
| Internals | INT | 14 | 11.7% | ✅ |
| Storage and Transforms | STOR | 11 | 9.2% | ✅ |
| Format System | FMT | 10 | 8.3% | ✅ |
| File Selection and Archives | SEL | 10 | 8.3% | ✅ |
| Extending Formats | EXT | 10 | 8.3% | ✅ |
| Delimited Formats (CSV/TSV) | DELIM | 9 | 7.5% | ✅ |
| Operations | OPS | 8 | 6.7% | ✅ |
| Errors | ERR | 8 | 6.7% | ✅ |
| Foundations | FOUND | 7 | 5.8% | ✅ |
| Schema Discovery | SCHEMA | 7 | 5.8% | ✅ |
| Writing and Append | WRITE | 6 | 5.0% | ✅ |
| File Specs | SPEC | 5 | 4.2% | ✅ |

## Visual Distribution

```
JSON, Parquet, Excel and  ██████  15 ( 12.5%)
Internals                 █████  14 ( 11.7%)
Storage and Transforms    ████  11 (  9.2%)
Format System             ████  10 (  8.3%)
File Selection and Archiv ████  10 (  8.3%)
Extending Formats         ████  10 (  8.3%)
Delimited Formats (CSV/TS ███   9 (  7.5%)
Operations                ███   8 (  6.7%)
Errors                    ███   8 (  6.7%)
Foundations               ██   7 (  5.8%)
Schema Discovery          ██   7 (  5.8%)
Writing and Append        ██   6 (  5.0%)
File Specs                ██   5 (  4.2%)
```

## Balance Analysis

### ✅ No Over-Represented Categories

All categories are under the 30% threshold. Good balance!

## Category Details

### JSON, Parquet, Excel and XML (FMTS)

**Count**: 15 concepts (12.5%)

**Concepts**:

- 61. JsonSpec
- 62. NDJSON
- 63. JSON Property Path
- 64. JSON Row Shapes
- 65. Inference Sample Rows
- 66. ParquetSpec
- 67. Parquet Column Projection
- 68. XlsxSpec
- 69. Sheet Selection
- 70. Excel Is Read-Only
- 71. Workbook Container Limits
- 72. XmlSpec
- 73. XPath Selection
- 74. lxml and ElementTree Fallback
- 75. Format Support Matrix

### Internals (INT)

**Count**: 14 concepts (11.7%)

**Concepts**:

- 107. Read Pipeline
- 108. Access Routing
- 109. Output Normalisation Seam
- 110. Format Registry Internals
- 111. Registration Bootstrap
- 112. Storage Boundary Principle
- 113. Lazy Import Invariant
- 114. Engine Type Normalisation
- 115. CSV Native Path vs Lexer
- 116. Safe CSV Field Encoding
- 117. ZIP Container Hardening
- 118. Append Merge Semantics
- 119. XLSX Calamine Reader
- 120. Package Version Source

### Storage and Transforms (STOR)

**Count**: 11 concepts (9.2%)

**Concepts**:

- 40. Storage Profile
- 41. Named Storage Profiles
- 42. Auth Profile
- 43. Location Policy
- 44. Transform Pipeline
- 45. Transform Inference (infer)
- 46. Gzip Transform
- 47. GPG Encryption Transform
- 48. Stream Access Modes
- 49. Range Policy
- 50. Remote URL Sources

### Format System (FMT)

**Count**: 10 concepts (8.3%)

**Concepts**:

- 13. Format Key
- 14. FormatSpec
- 15. Suffix Detection
- 16. Media Type Detection
- 17. Format Resolution Precedence
- 18. Transform Suffixes Skipped
- 19. Suffix Overrides
- 20. Format Options Round-Trip
- 21. Format Capability Flags
- 58. Temporal Inference

### File Selection and Archives (SEL)

**Count**: 10 concepts (8.3%)

**Concepts**:

- 30. Path Templates
- 31. Glob Patterns
- 32. Glob Segment Semantics
- 33. Missing Files (on_missing)
- 34. ZipArchive
- 35. ZIP Member Selection
- 36. Unrecognised Archive Members
- 37. GzipCompression
- 38. Decompression Limits
- 39. Skipped Members in Results

### Extending Formats (EXT)

**Count**: 10 concepts (8.3%)

**Concepts**:

- 97. register_format
- 98. FormatParser Protocol
- 99. FormatSerialiser Protocol
- 100. FormatSchemaInspector Protocol
- 101. Lazy Dotted-Path Registration
- 102. Entry-Point Plugins
- 103. Registration Override
- 104. Access Mode Registration
- 105. Import-Light Plugin Modules
- 106. COMPLEX_HANDLER_KEY Linkage

### Delimited Formats (CSV/TSV) (DELIM)

**Count**: 9 concepts (7.5%)

**Concepts**:

- 51. CsvSpec
- 52. Delimiter and Quoting Options
- 53. Null Sequence
- 54. Multi-Row Headers
- 55. Comment Rows
- 56. CSV Column Selection
- 57. CSV dtypes Overrides
- 59. Formula Neutralisation
- 60. TsvSpec

### Operations (OPS)

**Count**: 8 concepts (6.7%)

**Concepts**:

- 22. parse
- 23. ParseResult
- 24. Output Mode (arrow vs pydata)
- 25. parse_bytes
- 26. write
- 27. serialise_bytes
- 28. copy
- 29. stream

### Errors (ERR)

**Count**: 8 concepts (6.7%)

**Concepts**:

- 89. FormatError
- 90. UnknownFormatError
- 91. ParseError
- 92. FormatConflictError
- 93. WriteError
- 94. AppendSchemaMismatchError
- 95. MissingDependencyError
- 96. Archive Errors

### Foundations (FOUND)

**Count**: 7 concepts (5.8%)

**Concepts**:

- 1. Structured File
- 2. Arrow Table
- 3. Python Records
- 4. Tabular vs Non-Tabular Data
- 5. Storage Location
- 6. Optional Extras
- 7. mountainash-transport

### Schema Discovery (SCHEMA)

**Count**: 7 concepts (5.8%)

**Concepts**:

- 76. inspect_schema
- 77. SchemaResult
- 78. Schema Basis
- 79. infer_schema_rows Budget
- 80. inspect_schema_bytes
- 81. Footer-Only Parquet Schema
- 82. SchemaDiscoveryUnsupportedError

### Writing and Append (WRITE)

**Count**: 6 concepts (5.0%)

**Concepts**:

- 83. Write Disposition
- 84. Parquet Append
- 85. Append Schema Check
- 86. create_path
- 87. Format Conversion
- 88. Raw Bytes Write

### File Specs (SPEC)

**Count**: 5 concepts (4.2%)

**Concepts**:

- 8. FileSpec
- 9. FileSourceSpec
- 10. FileSinkSpec
- 11. Spec Format Field
- 12. Immutable Specs

## Recommendations

- ✅ **Excellent balance**: Categories are evenly distributed (spread: 8.3%)
- ✅ **MISC category minimal**: Good categorization specificity

### Educational Use Recommendations

- Use taxonomy categories for color-coding in graph visualizations
- Design curriculum modules based on taxonomy groupings
- Create filtered views for focused learning paths
- Use categories for assessment organization
- Enable navigation by topic area in interactive tools

---

*Report generated by ibook graph taxonomy-report*
