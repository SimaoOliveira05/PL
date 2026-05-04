# test_lexer.py
import pytest
from pathlib import Path
from conftest import lex_file

CASES = sorted((Path(__file__).parent / 'tests' / 'lexer').glob('*.f'))


@pytest.mark.parametrize('src', CASES, ids=[p.stem for p in CASES])
def test_lexer(src):
    expected = src.with_suffix('.expected').read_text().strip()
    result = lex_file(src)
    assert result == expected
