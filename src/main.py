# src/main.py
import sys
import pprint
import ply.lex as lex

from preprocessor import preprocess
from lexer import lexer
from parser import parser
from semantic import SemanticAnalyser as Analyser, SemanticError
from irgen import IRGenerator
from codegen import CodeGenerator
from optimizer import Optimizer


def _make_token(type_, value, lineno):
    """Create a synthetic PLY token (used to inject LABEL tokens)."""
    tok = lex.LexToken()
    tok.type   = type_
    tok.value  = value
    tok.lineno = lineno
    tok.lexpos = 0  
    return tok


class TokenStream:
    """
    Bridges preprocessor output → PLY parser.

    Iterates over logical lines produced by the preprocessor.
    For each line that carries a statement label (cols 1-5), a synthetic
    LABEL token is injected first; then all tokens from the lexer for that
    line's code body follow.  The parser receives one unified token stream
    covering the entire source file.
    """

    def __init__(self, logical_lines):
        self._tokens = []
        self._pos    = 0
        self.lineno  = 1
        self._build(logical_lines)

    def _build(self, logical_lines):
        for line in logical_lines:
            if line['label'] is not None:
                self._tokens.append(
                    _make_token('LABEL', int(line['label']), line['physical_line'])
                )
            lexer.input(line['code'])
            lexer.lineno = line['physical_line']
            for tok in lexer:
                self._tokens.append(tok)

    def token(self):
        """Called repeatedly by PLY's parser to fetch the next token."""
        if self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            self.lineno = tok.lineno
            self._pos += 1
            return tok
        return None


if __name__ == '__main__':
    args = sys.argv[1:]
    quiet = '-q' in args
    args = [a for a in args if a != '-q']

    if not args:
        print(f"Usage: python {sys.argv[0]} [-q] <source.f>")
        sys.exit(1)

    try:
        with open(args[0]) as f:
            logical_lines = preprocess(f)

        stream = TokenStream(logical_lines)
        ast = parser.parse(input=None, lexer=stream)

        if not quiet:
            print("=== AST ===")
            pprint.pprint(ast)

        sa = Analyser()
        result = sa.analyse(ast)

        if not quiet:
            print("\n=== Simple Semantic ===")
            print("Symbol table:", sa.symtab)
            pprint.pprint(result)

        ir_generator = IRGenerator()
        ir_list = ir_generator.generate(result)

        if not quiet:
            print("\n=== IR ===")
            for proc in ir_list:
                print(f"\n--- {proc.name} ---")
                for instr in proc.instructions:
                    print(instr)

        opt = Optimizer()
        ir_list = opt.optimize(ir_list)

        if not quiet:
            print("\n=== IR (optimized) ===")
            for proc in ir_list:
                print(f"\n--- {proc.name} ---")
                for instr in proc.instructions:
                    print(instr)

        cg = CodeGenerator()
        for proc in ir_list:
            cg.genProcedure(proc)

        if not quiet:
            print("\n=== VM Code ===")
        for line in cg.output:
            print(line)

    except (SyntaxError, SemanticError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

