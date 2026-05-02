# Testing Environment Design

**Date:** 2026-05-02
**Project:** Fortran 77 Compiler (PL coursework)

## Goal

Build an automated test suite that verifies each stage of the compiler pipeline independently, covering both valid programs and error cases. Tests are driven by `.f` snippet files — adding a test never requires editing Python.

## Architecture

### Directory Structure

```
tests/
  lexer/
    *.f  +  *.expected          # token list, one per line
  parser/
    *.f  +  *.expected          # pprint of AST
  semantic/
    valid/
      *.f  +  *.expected        # pprint of annotated AST + symtab
    errors/
      *.f  +  *.expected_error  # substring of expected error message
  ir/
    *.f  +  *.expected          # IR instructions, one per line
  codegen/
    *.f  +  *.expected          # VM code lines

conftest.py                     # shared pipeline helpers
test_lexer.py
test_parser.py
test_semantic.py
test_ir.py
test_codegen.py
```

### conftest.py — Pipeline Helpers

Five functions that run the pipeline up to the required stage, returning a string for comparison:

| Function | Input | Returns |
|---|---|---|
| `lex_file(path)` | `.f` path | token list as `TYPE` or `TYPE(value)`, one per line |
| `parse_file(path)` | `.f` path | `pprint.pformat(ast)` |
| `semantic_file(path)` | `.f` path | `pprint.pformat(annotated_ast)` + symtab |
| `ir_file(path)` | `.f` path | IR instructions as `str(instr)`, one per line |
| `compile_to_vm(path)` | `.f` path | VM code lines joined by `\n` |

### Test File Pattern

Every `test_*.py` uses `pytest.mark.parametrize` to auto-discover all `.f` files in its folder:

```python
CASES = sorted(Path("tests/lexer").glob("*.f"))

@pytest.mark.parametrize("src", CASES, ids=[p.stem for p in CASES])
def test_lexer(src):
    expected = src.with_suffix(".expected").read_text().strip()
    result = lex_file(src)
    assert result == expected
```

For semantic error cases:
```python
def test_semantic_error(src):
    expected_msg = src.with_suffix(".expected_error").read_text().strip()
    with pytest.raises(Exception, match=expected_msg):
        semantic_file(src)
```

### Expected File Formats

- **Lexer `.expected`**: one token per line, format `TYPE` or `TYPE(value)` — e.g. `INTEGER`, `ID(A)`, `REAL_LIT(3.14)`
- **Parser `.expected`**: `pprint.pformat` of the AST tuple tree
- **Semantic `.expected`**: `pprint.pformat` of annotated AST followed by symtab dict
- **IR `.expected`**: `str(instr)` for each instruction, one per line
- **Codegen `.expected`**: raw VM code, one instruction per line
- **Semantic `.expected_error`**: substring that must appear in the exception message

## Test Cases

### Lexer (`tests/lexer/`)

| File | Feature |
|---|---|
| `keywords.f` | All keywords: PROGRAM, INTEGER, REAL, LOGICAL, CHARACTER, DO, IF, THEN, ELSE, ENDIF, GOTO, READ, PRINT, CALL, RETURN, FUNCTION, SUBROUTINE, END |
| `operators.f` | Relational (`.EQ.` `.NE.` `.LT.` `.LE.` `.GT.` `.GE.`), logical (`.AND.` `.OR.` `.NOT.`), power (`**`) |
| `literals.f` | Integer, real (with decimal and exponent), string literal, `.TRUE.`/`.FALSE.` |
| `continuation.f` | Continuation line (col 6 non-space) appended to previous logical line |
| `comments.f` | Lines starting with `C` or `*` are ignored |
| `labels.f` | Statement labels in cols 1–5 produce LABEL token |

### Parser (`tests/parser/`)

| File | Feature |
|---|---|
| `decl.f` | Scalar and array declarations (INTEGER A, INTEGER B(10)) |
| `assign.f` | Simple assignment, array element assignment |
| `do_loop.f` | DO label var = start, end / CONTINUE |
| `if_else.f` | IF-THEN-ELSE-ENDIF and arithmetic IF |
| `goto.f` | GOTO label |
| `io.f` | READ \*, varlist and PRINT \*, exprlist |
| `call_or_arr.f` | Ambiguous `ID(expr)` in expression position |
| `subprogram.f` | FUNCTION and SUBROUTINE with RETURN |

### Semantic Valid (`tests/semantic/valid/`)

| File | Feature |
|---|---|
| `type_coerce.f` | Integer assigned to REAL variable — coerce node inserted |
| `array_access.f` | `call_or_arr` resolved to `arr_ref` via symtab |
| `func_call.f` | `call_or_arr` resolved to function call via symtab |
| `do_restructure.f` | Flat DO+CONTINUE restructured into nested loop |
| `nested_if.f` | Nested IF-THEN-ENDIF |
| `intrinsics.f` | MOD and other intrinsic functions |

### Semantic Errors (`tests/semantic/errors/`)

| File | Expected error |
|---|---|
| `undeclared.f` | `undeclared` (variable not in symtab) |
| `duplicate_decl.f` | `Duplicate` (same variable declared twice) |
| `type_mismatch.f` | `type` (incompatible operand types) |

### IR (`tests/ir/`)

| File | Feature |
|---|---|
| `arith_int.f` | Integer arithmetic — ADD/SUB/MUL/DIV instructions |
| `arith_real.f` | Real arithmetic — FADD/FSUB/FMUL/FDIV |
| `arith_mixed.f` | Mixed int/real — coerce instruction inserted |
| `do_loop.f` | DO loop produces label/jump/jz IR structure |
| `array_rw.f` | Array read (`load_arr`) and write (`store_arr`) |

### Codegen (`tests/codegen/`)

| File | Feature |
|---|---|
| `hello.f` | REAL variable, array, PRINT |
| `fatorial.f` | DO loop, READ, PRINT, integer arithmetic |
| `primo.f` | Nested IF, GOTO, LOGICAL variable, MOD |
| `somaarr.f` | Integer array, DO loop, READ into array |
| `conversor.f` | FUNCTION subprogram, CALL, RETURN |
| `basic_arith.f` | Basic integer and real arithmetic expressions |

## Running Tests

```bash
cd /home/simon/3Ano/PL/PL
pytest tests/ -v
# run a single stage
pytest test_codegen.py -v
```

## Constraints

- No VM execution — tests verify generated VM code text, not program runtime output
- Expected files are generated once by running the compiler on known-good inputs, then committed
- When the compiler output changes intentionally, regenerate the affected `.expected` files by running the compiler manually and overwriting them
