"""Qualify direct and sdist-rebuilt files wheels with isolated typed consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

from packaging.utils import parse_wheel_filename

PACKAGE = "mountainash_files"
DEPENDENCIES = {
    "mountainash-settings": "mountainash_settings",
    "mountainash-auth-client": "mountainash_auth_client",
    "mountainash-transport": "mountainash_transport",
}
TYPING_DEPENDENCIES = (
    "mypy==1.10.1",
    "pyarrow-stubs==20.0.0.20260819",
    "types-PyYAML==6.0.12.20260906",
    "lxml-stubs==0.5.1",
    "types-openpyxl==3.1.5.20260827",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def only(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern} in {directory}, got {len(matches)}")
    return matches[0]


def inspect_wheel(wheel: Path, module: str) -> None:
    with zipfile.ZipFile(wheel) as archive:
        if f"{module}/py.typed" not in archive.namelist():
            raise RuntimeError(f"{wheel.name} lacks {module}/py.typed")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="New evidence directory outside checkout"
    )
    parser.add_argument(
        "--dependency-wheels",
        type=Path,
        required=True,
        help="Directory containing exactly one wheel per required sibling",
    )
    args = parser.parse_args()
    output = (
        args.output.resolve()
        if args.output
        else Path(tempfile.mkdtemp(prefix="files-typing-"))
    )
    if output.is_relative_to(root):
        parser.error("--output must be outside the source checkout")
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    print(f"Typing qualification evidence: {output}", flush=True)
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PYTHON", "MYPY", "PIP_", "UV_")) or key in (
            "VIRTUAL_ENV",
            "HATCH_SIBLINGS",
        ):
            env.pop(key, None)
    receipt: dict = {
        "python": sys.version,
        "executable": sys.executable,
        "status": "failed",
    }
    wheels: dict[str, Path] = {}

    def run(
        command: list[str],
        cwd: Path,
        log: str,
        *,
        check: bool = True,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        (output / log).write_text("$ " + " ".join(command) + "\n" + result.stdout)
        if not quiet:
            print(result.stdout, end="", flush=True)
        if check:
            result.check_returncode()
        return result

    try:
        revision = run(
            ["git", "rev-parse", "HEAD"], root, "source-revision.log"
        ).stdout.strip()
        status = run(["git", "status", "--short"], root, "source-status.log").stdout
        run(["git", "diff", "--binary", "HEAD"], root, "source-diff.log", quiet=True)
        names = run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            root,
            "source-files.log",
            quiet=True,
        ).stdout.split("\0")
        receipt["source"] = {
            "revision": revision,
            "status": status,
            "files_sha256": {
                name: sha256(root / name)
                for name in sorted(set(names))
                if name and (root / name).is_file()
            },
        }
        for wheel in sorted(args.dependency_wheels.resolve().glob("*.whl")):
            name, _, _, _ = parse_wheel_filename(wheel.name)
            if name not in DEPENDENCIES:
                raise RuntimeError(f"Unexpected dependency wheel: {wheel.name}")
            if name in wheels:
                raise RuntimeError(f"Ambiguous dependency wheels for {name}")
            inspect_wheel(wheel, DEPENDENCIES[name])
            wheels[name] = wheel
        if set(wheels) != set(DEPENDENCIES):
            raise RuntimeError(
                f"Missing dependency wheels: {set(DEPENDENCIES) - set(wheels)}"
            )

        run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--sdist",
                "--outdir",
                str(output / "direct"),
                str(root),
            ],
            output,
            "build.log",
        )
        direct = only(output / "direct", "*.whl")
        sdist = only(output / "direct", "*.tar.gz")
        inspect_wheel(direct, PACKAGE)
        with tarfile.open(sdist) as archive:
            if not any(
                name.endswith(f"/src/{PACKAGE}/py.typed") for name in archive.getnames()
            ):
                raise RuntimeError("sdist lacks py.typed")
            archive.extractall(output / "source", filter="data")
        source = only(output / "source", "*")
        for recipe in ("tests/typing/consumer.py", "tools/qualify_typing.py"):
            if not (source / recipe).is_file():
                raise RuntimeError(f"sdist lacks qualification recipe: {recipe}")
        run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(output / "rebuilt"),
                str(source),
            ],
            output,
            "rebuild.log",
        )
        rebuilt = only(output / "rebuilt", "*.whl")
        inspect_wheel(rebuilt, PACKAGE)
        receipt["consumer_sha256"] = sha256(source / "tests/typing/consumer.py")
        receipt["cells"] = {}
        for kind, wheel in (("direct", direct), ("rebuilt", rebuilt)):
            consumer = output / f"consumer-{kind}"
            consumer.mkdir()
            shutil.copy(source / "tests/typing/consumer.py", consumer / "consumer.py")
            (consumer / "mypy.ini").write_text("[mypy]\n")
            environment = output / f"env-{kind}"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = str(
                environment
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            run(
                [
                    python,
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    str(wheel),
                    *(str(w) for w in wheels.values()),
                    *TYPING_DEPENDENCIES,
                ],
                consumer,
                f"{kind}-install.log",
            )
            run(
                [python, "-m", "pip", "--isolated", "freeze"],
                consumer,
                f"{kind}-dependencies.log",
            )
            origins = [
                ["mountainash-files", PACKAGE, str(wheel), sha256(wheel)],
                *(
                    [name, DEPENDENCIES[name], str(w), sha256(w)]
                    for name, w in wheels.items()
                ),
            ]
            origin_code = """
import importlib, importlib.metadata, json, pathlib, sys
result = {}
for name, module, wheel, digest in json.loads(sys.argv[1]):
    package = importlib.import_module(module)
    dist = importlib.metadata.distribution(name)
    origin = pathlib.Path(package.__file__).resolve()
    assert origin.is_relative_to(pathlib.Path(sys.prefix).resolve()), origin
    direct = json.loads(dist.read_text("direct_url.json"))
    assert direct["url"] == pathlib.Path(wheel).as_uri(), direct
    assert direct["archive_info"]["hashes"]["sha256"] == digest, direct
    result[name] = {"version": dist.version, "import_origin": str(origin), "direct_url": direct}
pathlib.Path("origins.json").write_text(json.dumps(result, indent=2) + "\\n")
print(json.dumps(result, indent=2))
import mountainash_files as m
pathlib.Path("exports.py").write_text("from mountainash_files import " + ", ".join(m.__all__) + "\\n")
"""
            run(
                [python, "-c", origin_code, json.dumps(origins)],
                consumer,
                f"{kind}-origins.log",
            )
            receipt["cells"][kind] = json.loads((consumer / "origins.json").read_text())
            checker = [
                python,
                "-m",
                "mypy",
                "--config-file",
                "mypy.ini",
                "--no-incremental",
                "--no-implicit-reexport",
                "--warn-unused-ignores",
                "--show-error-codes",
            ]
            run([*checker, "consumer.py", "exports.py"], consumer, f"{kind}-mypy.log")
            # Prove each expected rejection independently by removing its ignore.
            text = (consumer / "consumer.py").read_text()
            expected = {
                (number, match[1])
                for number, line in enumerate(text.splitlines(), 1)
                if (match := re.search(r"# type: ignore\[([\w-]+)\]", line))
            }
            if not expected:
                raise RuntimeError("No negative consumer contracts found")
            (consumer / "negative.py").write_text(
                re.sub(r"# type: ignore\[[\w-]+\]", "", text)
            )
            result = run(
                [*checker, "negative.py"], consumer, f"{kind}-negative.log", check=False
            )
            actual = {
                (int(line), code)
                for line, code in re.findall(
                    r"^negative.py:(\d+): error: .*\[([\w-]+)\]$",
                    result.stdout,
                    re.MULTILINE,
                )
            }
            if (
                result.returncode != 1
                or actual != expected
                or result.stdout.count(": error:") != len(expected)
            ):
                raise RuntimeError(
                    f"Unexpected negative diagnostics: expected {expected}, got {actual}"
                )
            run([python, "consumer.py"], consumer, f"{kind}-runtime.log")
        receipt["status"] = "passed"
    except Exception as exc:
        receipt["error"] = str(exc)
        raise
    finally:
        receipt["dependency_wheels"] = {str(w): sha256(w) for w in wheels.values()}
        receipt["artifacts"] = {
            str(p.relative_to(output)): sha256(p)
            for directory in ("direct", "rebuilt")
            for p in (output / directory).glob("*")
            if p.is_file()
        }
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
