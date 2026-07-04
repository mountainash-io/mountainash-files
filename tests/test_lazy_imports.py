"""Packaging invariant: importing the package must not import heavy libs."""
import subprocess
import sys


def test_top_level_import_stays_light():
    code = (
        "import sys; import mountainash_files; "
        "heavy = {'fastexcel', 'openpyxl', 'lxml', 'boto3', 'botocore', "
        "'paramiko'} & set(sys.modules); "
        "assert not heavy, f'heavy imports at top level: {heavy}'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
