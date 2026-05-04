# conftest.py
import sys
import pprint
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from preprocessor import preprocess
from lexer import lexer as _lexer
from parser import parser as _parser
from semantic import SemanticAnalyser
from irgen import IRGenerator
from codegen import CodeGenerator
import ply.lex as lex


def _make_token(type_, value, lineno):
    tok = lex.LexToken()
    tok.type = type_
    tok.value = value
    tok.lineno = lineno
    tok.lexpos = 0
    return tok


class _TokenStream:
    def __init__(self, logical_lines):
        self._tokens = []
        self._pos = 0
        self._build(logical_lines)

    def _build(self, logical_lines):
        for line in logical_lines:
            if line['label'] is not None:
                self._tokens.append(
                    _make_token('LABEL', int(line['label']), line['physical_line'])
                )
            _lexer.input(line['code'])
            _lexer.lineno = line['physical_line']
            for tok in _lexer:
                self._tokens.append(tok)

    def token(self):
        if self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            self._pos += 1
            return tok
        return None


def _preprocess(path):
    with open(path) as f:
        return preprocess(f)


def lex_file(path):
    """Tokenise path and return one token per line as TYPE or TYPE(value)."""
    logical_lines = _preprocess(path)
    tokens = []
    for line in logical_lines:
        if line['label'] is not None:
            tokens.append(f"LABEL({int(line['label'])})")
        _lexer.input(line['code'])
        _lexer.lineno = line['physical_line']
        for tok in _lexer:
            if tok.type in ('ID', 'INTEGER_LIT', 'REAL_LIT', 'STRING_LIT'):
                tokens.append(f"{tok.type}({tok.value})")
            else:
                tokens.append(tok.type)
    return '\n'.join(tokens)


def parse_file(path):
    """Parse path and return pprint of AST."""
    logical_lines = _preprocess(path)
    stream = _TokenStream(logical_lines)
    ast = _parser.parse(input=None, lexer=stream)
    return pprint.pformat(ast)


def semantic_file(path):
    """Run semantic analysis and return pprint of annotated AST, then symtab."""
    logical_lines = _preprocess(path)
    stream = _TokenStream(logical_lines)
    ast = _parser.parse(input=None, lexer=stream)
    sa = SemanticAnalyser()
    result = sa.analyse(ast)
    return pprint.pformat(result) + '\n---\n' + pprint.pformat(sa.symtab)


def ir_file(path):
    """Generate IR and return one instruction per line."""
    logical_lines = _preprocess(path)
    stream = _TokenStream(logical_lines)
    ast = _parser.parse(input=None, lexer=stream)
    sa = SemanticAnalyser()
    result = sa.analyse(ast)
    ir_gen = IRGenerator()
    ir_list = ir_gen.generate(result)
    lines = []
    for proc in ir_list:
        for instr in proc.instructions:
            lines.append(str(instr))
    return '\n'.join(lines)


def compile_to_vm(path):
    """Run full pipeline and return VM code lines."""
    logical_lines = _preprocess(path)
    stream = _TokenStream(logical_lines)
    ast = _parser.parse(input=None, lexer=stream)
    sa = SemanticAnalyser()
    result = sa.analyse(ast)
    ir_gen = IRGenerator()
    ir_list = ir_gen.generate(result)
    cg = CodeGenerator()
    for proc in ir_list:
        cg.genProcedure(proc)
    return '\n'.join(cg.output)
