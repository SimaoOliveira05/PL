# FortradUM

Fortran 77 compiler developed for a Programming Languages course. Written in Python using PLY (lex + yacc), it translates fixed-format Fortran 77 source into assembly for a course-provided virtual machine, passing through lexical analysis, syntactic analysis, semantic analysis, IR generation, optimisation, and code generation.

## Pipeline

```
.f source → preprocessor → lexer → parser → semantic → irgen → optimizer → codegen → VM assembly
```

## Features

- **Full Fortran 77 fixed-format support** — column rules, continuation lines, statement labels
- **Type system** — `INTEGER`, `REAL`, `LOGICAL`, `CHARACTER`, implicit coercion
- **Control flow** — `IF`/`THEN`/`ELSE`/`ENDIF`, `DO` loops (positive and negative step), `GOTO`
- **Subprograms** — `SUBROUTINE` and typed `FUNCTION`, recursive calls, array parameters
- **I/O** — `READ *` and `PRINT *`
- **Optimiser** — constant folding, copy propagation, dead-code elimination, temp forwarding

## Grade

**Final Grade:** TBD / 20

## Authors

- *Gabriel Dantas* → [@gabil88](https://github.com/gabil88)
- *José Fernandes* → [@JoseLourencoFernandes](https://github.com/JoseLourencoFernandes)
- *Simão Oliveira* → [@SimaoOliveira05](https://github.com/SimaoOliveira05)

## Requirements

- Python 3.10+
- PLY (`pip install ply`)
- pytest (for running the test suite)

## Running

Compile a Fortran source file and print the full pipeline output (AST, symbol table, IR, optimised IR, VM assembly):

```bash
python src/main.py tests/hello.f
```

Quiet mode — only the final VM assembly, suitable for piping into the VM:

```bash
python src/main.py -q tests/hello.f
```

Compile all test files:

```bash
for f in tests/*.f tests/extra/*.f; do echo "=== $f ==="; python src/main.py -q "$f"; done
```

## Tests

```bash
python -m pytest tests/
```

The test suite compiles each `.f` file and compares the output against the paired `.expected` snapshot.

| Test | Description |
|------|-------------|
| `hello.f` | Hello World |
| `fatorial.f` | Recursive factorial |
| `primo.f` | Primality test with DO loop |
| `somaarr.f` | Array sum |
| `conversor.f` | Type conversion |
| `dynarr.f` | Dynamic arrays |
| `funcall.f` | Function calls |
| `extra/coerce.f` | Integer→Real coercion |
| `extra/do_step.f` | DO loop with non-unit step |
| `extra/nested_do.f` | Nested DO loops |
| `extra/subroutine.f` | Subroutine call |
| `extra/logical_ops.f` | Logical operators |
| `extra/real_arith.f` | Real arithmetic |
| `extra/unary_minus.f` | Unary minus |
| `extra/ge_ne.f` | Relational operators |
