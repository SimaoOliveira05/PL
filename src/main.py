# src/main.py
import sys
from preprocessor import preprocess
from lexer import lexer

with open(sys.argv[1]) as f:
    logical_lines = preprocess(f)

for line in logical_lines:
    print(f"\n--- line {line['physical_line']} | label: {line['label']} ---")
    lexer.input(line['code'])
    lexer.lineno = line['physical_line']  # set the line number from the preprocessor
    for tok in lexer:
        print(tok)