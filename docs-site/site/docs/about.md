---
title: 'About'
description: 'What mountainash-files is for, where it fits in the mountainash ecosystem, its release status, who maintains it and how it is licensed'
---

[← Back to Home](index.md)

# About mountainash-files

**PyArrow, Polars and the format libraries read each file type. mountainash-files puts one spec-driven API in front of them, on any store mountainash-transport reaches.**

!!! warning "Experimental"
    mountainash-files 0.1.0 is experimental and not yet ready for production use. Its APIs can change between versions, and it is not yet published on PyPI.

## What it is for

mountainash-files gives a Python program one way to read and write structured files, whatever their format and wherever they are stored. A spec names the file, its format options, a storage profile and any compression or encryption transforms. `parse`, `write` and `inspect_schema` act on that spec, and tabular reads return Arrow tables or Python records. [Why mountainash-files](why.md) describes the three capabilities that set it apart.

## Where it fits

mountainash-files is one of six packages in the [mountainash ecosystem](https://docs.mountainash.io/). It reads and writes bytes through [mountainash-transport](https://docs.mountainash.io/mountainash-transport/), which reaches local disk, S3-compatible stores, SFTP and HTTP(S), and it keeps format handling out of that package. [mountainash](https://docs.mountainash.io/mountainash/) uses it for file resources through its `files` and `ibis` extras.

## Who maintains it

mountainash-files is written and maintained by Nathaniel Ramm. The code is at [github.com/mountainash-io/mountainash-files](https://github.com/mountainash-io/mountainash-files). Contributions arrive as pull requests against the `develop` branch, as described in [CONTRIBUTING.md](https://github.com/mountainash-io/mountainash-files/blob/develop/CONTRIBUTING.md). For questions, see [Contact](contact.md).

## License

mountainash-files, including this documentation, is licensed under the Apache License, Version 2.0, copyright 2024-2026 Mountain Ash Solutions Pty. Ltd. The [License](license.md) page has the details.
