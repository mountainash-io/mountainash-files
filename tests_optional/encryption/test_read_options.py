"""Real GPG qualification; requires python-gnupg and the GnuPG executable."""

import gzip
import subprocess

import gnupg
import pytest
from mountainash_transport import GPG

from mountainash_files import FileSinkSpec, FileSourceSpec, copy, parse


@pytest.fixture(scope="module")
def encrypted_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("encrypted-read-options")
    home = root / "keyring"
    home.mkdir(mode=0o700)
    client = gnupg.GPG(gnupghome=str(home))
    try:
        key = client.gen_key(client.gen_key_input(
            key_type="RSA", key_length=1024,
            name_email="files-test@example.invalid", no_protection=True,
        ))
        assert key.fingerprint, "GPG test key generation failed"
        for suffix, payload in (
            (".gpg", b"x\n1\n"),
            (".gz.gpg", gzip.compress(b"x\n1\n")),
        ):
            result = client.encrypt(payload, [key.fingerprint], always_trust=True)
            assert result.ok, result.status
            (root / ("rows.csv" + suffix)).write_bytes(result.data)
        yield root, GPG(gnupghome=str(home))
    finally:
        subprocess.run(
            ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
            check=True,
        )


@pytest.mark.parametrize("suffix", [".gpg", ".gz.gpg"])
def test_inferred_encryption_parse_and_copy(encrypted_sources, tmp_path, suffix):
    root, decoder = encrypted_sources
    source = FileSourceSpec(path=str(root / ("rows.csv" + suffix)), gpg=decoder)
    assert parse(source, output="pydata")[0].data == [{"x": 1}]
    destination = tmp_path / "plain.csv"
    copy(source, FileSinkSpec(path=str(destination)))
    assert destination.read_bytes() == b"x\n1\n"


def test_encrypted_glob_retains_key_configuration(encrypted_sources):
    root, decoder = encrypted_sources
    results = parse(
        FileSourceSpec(path=str(root), glob="rows.csv*", gpg=decoder),
        output="pydata",
    )
    assert [result.data for result in results] == [[{"x": 1}], [{"x": 1}]]
