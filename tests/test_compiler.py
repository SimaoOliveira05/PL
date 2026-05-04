"""End-to-end snapshot tests: compile each .f file and compare VM output."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MAIN = ROOT / "src" / "main.py"
TESTS_DIR = Path(__file__).parent


def _collect():
    cases = []
    for f in sorted(TESTS_DIR.glob("*.f")):
        cases.append(pytest.param(f, id=f.stem))
    for f in sorted((TESTS_DIR / "extra").glob("*.f")):
        cases.append(pytest.param(f, id=f"extra/{f.stem}"))
    return cases


@pytest.mark.parametrize("src", _collect())
def test_vm_output(src):
    expected_file = src.with_suffix(".expected")
    assert expected_file.exists(), f"Missing expected file: {expected_file}"

    result = subprocess.run(
        [sys.executable, str(MAIN), "-q", str(src)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Compiler error:\n{result.stderr}"
    assert result.stdout == expected_file.read_text(), (
        f"VM output mismatch for {src.name}"
    )
