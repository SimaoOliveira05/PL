#!/usr/bin/env python3
"""Regenerate all .expected files from the current compiler output.
Run from the project root: python scripts/gen_expected.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import lex_file, parse_file, semantic_file, ir_file, compile_to_vm

ROOT = Path(__file__).parent.parent / 'tests'


def gen(func, src):
    out = src.with_suffix('.expected')
    out.write_text(func(src).strip() + '\n')
    print(f'  wrote {out.relative_to(Path(__file__).parent.parent)}')


sections = [
    ('Lexer',           ROOT / 'lexer',           lex_file),
    ('Parser',          ROOT / 'parser',           parse_file),
    ('Semantic valid',  ROOT / 'semantic' / 'valid', semantic_file),
    ('IR',              ROOT / 'ir',               ir_file),
    ('Codegen',         ROOT / 'codegen',          compile_to_vm),
]

for label, folder, func in sections:
    print(f'{label}...')
    for f in sorted(folder.glob('*.f')):
        gen(func, f)

print('Done.')
