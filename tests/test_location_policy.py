import pytest
from mountainash_files import FileSinkSpec, FileSourceSpec, copy, inspect_schema, parse, stream, write
from mountainash_transport.location import LocationNotAllowed, LocationPolicy


def _s3_profile(bucket):
    from mountainash_auth_client import NoAuthProfile
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    from mountainash_transport.settings.storage.profiles import S3StorageProfile

    return S3StorageProfile(
        PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.S3,
        FLAVOR="aws",
        REGION="us-east-1",
        BUCKET=bucket,
        auth=NoAuthProfile(),
    )


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "root"; out = tmp_path / "out"; root.mkdir(); out.mkdir()
    (root / "a.csv").write_text("v\n1\n"); (out / "s.csv").write_text("v\n9\n")
    return root, out, LocationPolicy(root=str(root))


def test_parse_inside_root_reads(env):
    root, _, pol = env
    assert parse(FileSourceSpec(path="a.csv", format="csv", policy=pol))[0].data.num_rows == 1


@pytest.mark.parametrize("op", ["parse", "inspect_schema", "stream"])
def test_read_operations_reject_outside(env, op):
    _, out, pol = env
    spec = FileSourceSpec(path=str(out / "s.csv"), format="csv", policy=pol)
    with pytest.raises(LocationNotAllowed):
        r = {"parse": parse, "inspect_schema": inspect_schema, "stream": stream}[op](spec)
        if op == "stream":
            r.__enter__()


def test_template_expansion_escape_rejected(env):
    _, _, pol = env
    with pytest.raises(LocationNotAllowed):
        parse(FileSourceSpec(path="{p}", format="csv", policy=pol), params={"p": "../out/s.csv"})


def test_glob_reads_only_in_root(env):
    root, out, pol = env
    (root / "link.csv").symlink_to(out / "s.csv")
    with pytest.raises(LocationNotAllowed):
        parse(FileSourceSpec(path=".", glob="*.csv", format="csv", policy=pol))


@pytest.mark.parametrize("mode", ["replace", "append"])
def test_write_outside_rejected(env, mode):
    import pyarrow as pa
    _, out, pol = env
    with pytest.raises(LocationNotAllowed):
        write(FileSinkSpec(path=str(out / "w.parquet"), format="parquet", policy=pol, write_disposition=mode), pa.table({"v": [1]}))


def test_copy_each_endpoint_uses_its_own_policy(env, tmp_path):
    root, out, pol = env
    dst = tmp_path / "dst"; dst.mkdir()
    copy(FileSourceSpec(path="a.csv", policy=pol), FileSinkSpec(path="b.csv", policy=LocationPolicy(root=str(dst))))
    assert (dst / "b.csv").exists()
    with pytest.raises(LocationNotAllowed):
        copy(FileSourceSpec(path="a.csv", policy=pol), FileSinkSpec(path=str(out / "x.csv"), policy=LocationPolicy(root=str(dst))))
    with pytest.raises(LocationNotAllowed):
        copy(FileSourceSpec(path=str(out / "s.csv"), policy=pol), FileSinkSpec(path="c.csv", policy=LocationPolicy(root=str(dst))))


def test_no_policy_is_today(env):
    _, out, _ = env
    assert parse(FileSourceSpec(path=str(out / "s.csv"), format="csv"))[0].data.num_rows == 1


def test_unknown_scheme_rejected_and_redacted(env):
    _, _, pol = env
    with pytest.raises(LocationNotAllowed) as e:
        parse(FileSourceSpec(path="hf://user:secret@h/x.csv", format="csv", policy=pol))
    assert "secret" not in str(e.value)


def test_supplied_profile_permits_its_own_endpoint_only(env, monkeypatch):
    """Decision 3 at the files boundary: a supplied S3 profile with BUCKET permits that bucket only."""
    import io
    from mountainash_transport.storage.facade import facade as facade_mod
    reads = []

    class Conn:
        def connect(self): pass
        def close(self): pass

    class Backend:
        storage_profile = None
        def read_to_bytes(self, path): reads.append(path); return b"v\n1\n"
        def read_to_stream(self, path): reads.append(path); return io.BytesIO(b"v\n1\n")

    monkeypatch.setattr("mountainash_transport.connections.create_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(facade_mod, "get_storage_backend", lambda *a, **k: Backend())
    profile = _s3_profile(bucket="bucket-a")
    pol = LocationPolicy()
    parse(FileSourceSpec(path="s3://bucket-a/a.csv", format="csv", storage_profile=profile, policy=pol))
    with pytest.raises(LocationNotAllowed):
        parse(FileSourceSpec(path="s3://bucket-b/a.csv", format="csv", storage_profile=profile, policy=pol))
    assert reads == ["s3://bucket-a/a.csv"]


@pytest.mark.parametrize("op", ["parse", "inspect_schema", "stream"])
def test_denied_credential_gpg_url_redacted_before_inference(op):
    spec = FileSourceSpec(path="https://user:secret@denied.example/data.parquet.gpg", format="parquet",
                          policy=LocationPolicy())
    with pytest.raises(LocationNotAllowed) as e:
        r = {"parse": parse, "inspect_schema": inspect_schema, "stream": stream}[op](spec)
        if op == "stream":
            r.__enter__()
    assert "secret" not in str(e.value)
