# src/parser.py
import ply.yacc as yacc
from lexer import tokens as _lexer_tokens
from ast_nodes import (
    Program, Function, Subroutine,
    Scalar, Array, Decl,
    Assign, If, Goto, Continue, Return, Read, Print,
    CallStmt, Labeled, Do,
    IntLit, RealLit, StrLit, BoolLit,
    Var, ArrRef, Binop, Unary, CallOrArr,
)

# LABEL is injected synthetically by TokenStream (not matched by the lexer),
# so we extend the token list here rather than adding it to lexer.py.
tokens = _lexer_tokens + ('LABEL',)

start = 'file'

# ── Operator precedence (lowest → highest) ───────────────────────────────────
precedence = (
    ('left',     'OR'),
    ('left',     'AND'),
    ('right',    'NOT'),
    ('nonassoc', 'EQ', 'NE', 'LT', 'LE', 'GT', 'GE'),
    ('left',     '+', '-'),
    ('left',     '*', '/'),
    ('right',    'UMINUS'),
    ('right',    'POWER'),
)

# ── File / Program units ──────────────────────────────────────────────────────

def p_file(p):
    '''
    file : file program_unit
         | program_unit
    '''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

def p_program_unit(p):
    '''
    program_unit : main_program
                 | function_def
                 | subroutine_def
    '''
    p[0] = p[1]

def p_main_program(p):
    '''
    main_program : PROGRAM ID stmt_list END
                 | stmt_list END
    '''
    if len(p) == 5:
        p[0] = Program(name=p[2], body=p[3])
    else:
        p[0] = Program(name=None, body=p[1])

# ── FUNCTION / SUBROUTINE definitions ────────────────────────────────────────

def p_function_def(p):
    '''
    function_def : type_kw FUNCTION ID '(' param_list ')' stmt_list END
                 | type_kw FUNCTION ID '(' ')' stmt_list END
    '''
    if len(p) == 9:
        p[0] = Function(return_type=p[1], name=p[3], params=p[5], body=p[7])
    else:
        p[0] = Function(return_type=p[1], name=p[3], params=[], body=p[6])

def p_subroutine_def(p):
    '''
    subroutine_def : SUBROUTINE ID '(' param_list ')' stmt_list END
                   | SUBROUTINE ID '(' ')' stmt_list END
    '''
    if len(p) == 8:
        p[0] = Subroutine(name=p[2], params=p[4], body=p[6])
    else:
        p[0] = Subroutine(name=p[2], params=[], body=p[5])

def p_param_list(p):
    '''
    param_list : param_list ',' ID
               | ID
    '''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

# ── Statement list ────────────────────────────────────────────────────────────

def p_stmt_list_many(p):
    'stmt_list : stmt_list stmt'
    p[0] = p[1] + [p[2]]

def p_stmt_list_one(p):
    'stmt_list : stmt'
    p[0] = [p[1]]

# ── Statements ────────────────────────────────────────────────────────────────

def p_stmt_labeled(p):
    'stmt : LABEL unlabeled_stmt'
    p[0] = Labeled(label=p[1], stmt=p[2], lineno=p.lineno(1))

def p_stmt_unlabeled(p):
    'stmt : unlabeled_stmt'
    p[1].lineno = p.lineno(1)
    p[0] = p[1]

def p_unlabeled_stmt(p):
    '''
    unlabeled_stmt : decl_stmt
                   | assign_stmt
                   | if_stmt
                   | do_stmt
                   | goto_stmt
                   | read_stmt
                   | print_stmt
                   | continue_stmt
                   | return_stmt
                   | call_stmt
    '''
    p[0] = p[1]

# ── Type declarations ─────────────────────────────────────────────────────────

def p_decl_stmt(p):
    'decl_stmt : type_kw var_decl_list'
    p[0] = Decl(type=p[1], decls=p[2])

def p_type_kw(p):
    '''
    type_kw : INTEGER
            | REAL
            | LOGICAL
    '''
    p[0] = p[1]

def p_var_decl_list_many(p):
    "var_decl_list : var_decl_list ',' var_decl"
    p[0] = p[1] + [p[3]]

def p_var_decl_list_one(p):
    'var_decl_list : var_decl'
    p[0] = [p[1]]

def p_var_decl_scalar(p):
    'var_decl : ID'
    p[0] = Scalar(name=p[1])

def p_var_decl_array(p):
    '''
    var_decl : ID '(' INTEGER_LIT ')'
             | ID '(' ID ')'
    '''
    p[0] = Array(name=p[1], size=p[3])

# ── Assignment ────────────────────────────────────────────────────────────────

def p_assign_stmt_scalar(p):
    "assign_stmt : ID '=' expr"
    p[0] = Assign(lhs=Var(name=p[1]), rhs=p[3])

def p_assign_stmt_array(p):
    "assign_stmt : ID '(' expr ')' '=' expr"
    p[0] = Assign(lhs=ArrRef(name=p[1], idx=p[3]), rhs=p[6])

# ── IF statement ──────────────────────────────────────────────────────────────

def p_if_stmt(p):
    '''
    if_stmt : IF '(' expr ')' THEN stmt_list ENDIF
            | IF '(' expr ')' THEN stmt_list ELSE stmt_list ENDIF
    '''
    if len(p) == 8:
        p[0] = If(cond=p[3], then_body=p[6], else_body=None)
    else:
        p[0] = If(cond=p[3], then_body=p[6], else_body=p[8])

# ── DO statement ──────────────────────────────────────────────────────────────
# Only the header is parsed here. The body is the surrounding flat stmt_list,
# terminated by the labeled CONTINUE. Semantic analysis restructures this into
# a proper nested loop.

def p_do_stmt(p):
    '''
    do_stmt : DO INTEGER_LIT ID '=' expr ',' expr ',' expr
            | DO INTEGER_LIT ID '=' expr ',' expr
    '''
    if len(p) == 10:
        p[0] = Do(label=p[2], var=p[3], start=p[5], end=p[7], step=p[9])
    else:
        p[0] = Do(label=p[2], var=p[3], start=p[5], end=p[7], step=None)

# ── CONTINUE / RETURN / CALL / GOTO ──────────────────────────────────────────

def p_continue_stmt(p):
    'continue_stmt : CONTINUE'
    p[0] = Continue()

def p_return_stmt(p):
    'return_stmt : RETURN'
    p[0] = Return()

def p_call_stmt(p):
    '''
    call_stmt : CALL ID '(' expr_list ')'
              | CALL ID
    '''
    if len(p) == 6:
        p[0] = CallStmt(name=p[2], args=p[4])
    else:
        p[0] = CallStmt(name=p[2], args=[])

def p_goto_stmt(p):
    'goto_stmt : GOTO INTEGER_LIT'
    p[0] = Goto(label=p[2])

# ── READ / PRINT ──────────────────────────────────────────────────────────────

def p_read_stmt(p):
    "read_stmt : READ '*' ',' var_list"
    p[0] = Read(targets=p[4])

def p_var_list(p):
    '''
    var_list : var_list ',' lvalue
             | lvalue
    '''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_lvalue(p):
    '''
    lvalue : ID '(' expr ')'
           | ID
    '''
    if len(p) == 5:
        p[0] = ArrRef(name=p[1], idx=p[3])
    else:
        p[0] = Var(name=p[1])

def p_print_stmt(p):
    "print_stmt : PRINT '*' ',' expr_list"
    p[0] = Print(values=p[4])

def p_expr_list(p):
    '''
    expr_list : expr_list ',' expr
              | expr
    '''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

# ── Expressions ───────────────────────────────────────────────────────────────

def p_expr_binop(p):
    '''
    expr : expr '+' expr
         | expr '-' expr
         | expr '*' expr
         | expr '/' expr
         | expr POWER expr
         | expr EQ expr
         | expr NE expr
         | expr LT expr
         | expr LE expr
         | expr GT expr
         | expr GE expr
         | expr AND expr
         | expr OR expr
    '''
    p[0] = Binop(op=p[2], left=p[1], right=p[3])

def p_expr_not(p):
    'expr : NOT expr'
    p[0] = Unary(op='NOT', operand=p[2])

def p_expr_uminus(p):
    "expr : '-' expr %prec UMINUS"
    p[0] = Unary(op='-', operand=p[2])

def p_expr_group(p):
    "expr : '(' expr ')'"
    p[0] = p[2]

def p_expr_atom(p):
    '''
    expr : INTEGER_LIT
         | REAL_LIT
         | STRING_LIT
         | TRUE
         | FALSE
         | ID
    '''
    t = p.slice[1].type
    if t == 'INTEGER_LIT':
        p[0] = IntLit(value=p[1])
    elif t == 'REAL_LIT':
        p[0] = RealLit(value=p[1])
    elif t == 'STRING_LIT':
        p[0] = StrLit(value=p[1])
    elif t == 'TRUE':
        p[0] = BoolLit(value=True)
    elif t == 'FALSE':
        p[0] = BoolLit(value=False)
    else:
        p[0] = Var(name=p[1])

# Covers both array element access (e.g. NUMS(I)) and function calls
# (e.g. CONVRT(N, B)). Disambiguated later in semantic analysis.
def p_expr_call_or_arr(p):
        "expr : ID '(' expr_list ')'"
        p[0] = CallOrArr(name=p[1], args=p[3])

# ── Error handler ─────────────────────────────────────────────────────────────

def p_error(p):
    if p:
        raise SyntaxError(f"Syntax error at '{p.value}' (type: {p.type}) on line {p.lineno}")
    else:
        raise SyntaxError("Syntax error: unexpected end of input")

# ── Build ─────────────────────────────────────────────────────────────────────

parser = yacc.yacc()
