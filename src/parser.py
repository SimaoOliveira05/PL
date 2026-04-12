# src/parser.py
import ply.yacc as yacc
from lexer import tokens as _lexer_tokens

# LABEL is injected synthetically by TokenStream (not matched by the lexer),
# so we extend the token list here rather than adding it to lexer.py.
tokens = _lexer_tokens + ('LABEL',)

start = 'file'

# ── Operator precedence (lowest → highest) ───────────────────────────────────
# Mirrors standard Fortran 77 precedence.
precedence = (
    ('left',     'OR'),
    ('left',     'AND'),
    ('right',    'NOT'),
    ('nonassoc', 'EQ', 'NE', 'LT', 'LE', 'GT', 'GE'),
    ('left',     '+', '-'),
    ('left',     '*', '/'),
    ('right',    'UMINUS'), # UMINUS não é um token real — é um pseudo-token usado só na tabela de precedência para dar ao - unário (como em -X) precedência maior que a adição, via %prec UMINUS na regra.
    ('right',    'POWER'),
)

# ── File / Program units ──────────────────────────────────────────────────────
# A Fortran 77 source file is one or more program units: a main program,
# a FUNCTION subprogram, or a SUBROUTINE subprogram.

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
        p[0] = ('program', p[2], p[3])
    else:
        p[0] = ('program', None, p[1])

# ── FUNCTION / SUBROUTINE definitions ────────────────────────────────────────

def p_function_def(p):
    '''
    function_def : type_kw FUNCTION ID '(' param_list ')' stmt_list END
                 | type_kw FUNCTION ID '(' ')' stmt_list END
    '''
    if len(p) == 9:
        p[0] = ('function', p[1], p[3], p[5], p[7])
    else:
        p[0] = ('function', p[1], p[3], [], p[6])

def p_subroutine_def(p):
    '''
    subroutine_def : SUBROUTINE ID '(' param_list ')' stmt_list END
                   | SUBROUTINE ID '(' ')' stmt_list END
    '''
    if len(p) == 8:
        p[0] = ('subroutine', p[2], p[4], p[6])
    else:
        p[0] = ('subroutine', p[2], [], p[5])

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
    '''
    stmt_list : stmt_list stmt
    '''
    p[0] = p[1] + [p[2]]

def p_stmt_list_one(p):
    '''
    stmt_list : stmt
    '''
    p[0] = [p[1]]

# ── Statements ────────────────────────────────────────────────────────────────

def p_stmt_labeled(p):
    '''
    stmt : LABEL unlabeled_stmt
    '''
    p[0] = ('labeled', p[1], p[2])

def p_stmt_unlabeled(p):
    '''
    stmt : unlabeled_stmt
    '''
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
# Handles: INTEGER A, B  and  INTEGER A(5), B(3)

def p_decl_stmt(p):
    '''
    decl_stmt : type_kw var_decl_list
    '''
    p[0] = ('decl', p[1], p[2])

def p_type_kw(p):
    '''
    type_kw : INTEGER
            | REAL
            | LOGICAL
            | CHARACTER
    '''
    p[0] = p[1]

def p_var_decl_list_many(p):
    '''
    var_decl_list : var_decl_list ',' var_decl
    '''
    p[0] = p[1] + [p[3]]

def p_var_decl_list_one(p):
    '''
    var_decl_list : var_decl
    '''
    p[0] = [p[1]]

def p_var_decl_scalar(p):
    '''
    var_decl : ID
    '''
    p[0] = ('scalar', p[1])

def p_var_decl_array(p):
    '''
    var_decl : ID '(' INTEGER_LIT ')'
    '''
    p[0] = ('array', p[1], p[3])

# ── Assignment ────────────────────────────────────────────────────────────────

def p_assign_stmt_scalar(p):
    '''
    assign_stmt : ID '=' expr
    '''
    p[0] = ('assign', ('var', p[1]), p[3])

def p_assign_stmt_array(p):
    '''
    assign_stmt : ID '(' expr ')' '=' expr
    '''
    p[0] = ('assign', ('arr_ref', p[1], p[3]), p[6])

# ── IF statement ──────────────────────────────────────────────────────────────

def p_if_stmt(p):
    '''
    if_stmt : IF '(' expr ')' THEN stmt_list ENDIF
            | IF '(' expr ')' THEN stmt_list ELSE stmt_list ENDIF
    '''
    if len(p) == 8:
        p[0] = ('if', p[3], p[6], None)
    else:
        p[0] = ('if', p[3], p[6], p[8])

# ── DO statement ──────────────────────────────────────────────────────────────
# Only the header is parsed here. The body is the surrounding flat stmt_list,
# terminated by the labeled CONTINUE. Semantic analysis restructures this into
# a proper nested loop. This avoids a shift/reduce conflict that would arise
# if we tried to match the body inline in LALR(1).
#
# Supports optional step:  DO 10 I = 1, N       (step defaults to 1)
#                          DO 10 I = 1, N, 2    (explicit step)

def p_do_stmt(p):
    '''
    do_stmt : DO INTEGER_LIT ID '=' expr ',' expr ',' expr
            | DO INTEGER_LIT ID '=' expr ',' expr
    '''
    # O passo é marcado como None em vez de ('int', 1) porque o parser
    # deve representar fielmente o que está no código fonte, sem inventar
    # valores. A distinção entre "passo omitido" e "passo explícito de 1"
    # é preservada para a análise semântica, que aplica o default quando
    # necessário.
    if len(p) == 10:
        p[0] = ('do', p[2], p[3], p[5], p[7], p[9])
    else:
        p[0] = ('do', p[2], p[3], p[5], p[7], None)

# ── CONTINUE ──────────────────────────────────────────────────────────────────

def p_continue_stmt(p):
    '''
    continue_stmt : CONTINUE
    '''
    p[0] = ('continue',)

# ── RETURN ────────────────────────────────────────────────────────────────────

def p_return_stmt(p):
    '''
    return_stmt : RETURN
    '''
    p[0] = ('return',)

# ── CALL ──────────────────────────────────────────────────────────────────────

def p_call_stmt(p):
    '''
    call_stmt : CALL ID '(' expr_list ')'
              | CALL ID
    '''
    if len(p) == 6:
        p[0] = ('call', p[2], p[4])
    else:
        p[0] = ('call', p[2], [])

# ── GOTO ──────────────────────────────────────────────────────────────────────

def p_goto_stmt(p):
    '''
    goto_stmt : GOTO INTEGER_LIT
    '''
    p[0] = ('goto', p[2])

# ── READ ──────────────────────────────────────────────────────────────────────
# READ *, var, var, ...

def p_read_stmt(p):
    '''
    read_stmt : READ '*' ',' var_list
    '''
    p[0] = ('read', p[4])

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
        p[0] = ('arr_ref', p[1], p[3])
    else:
        p[0] = ('var', p[1])

# ── PRINT ─────────────────────────────────────────────────────────────────────
# PRINT *, expr, expr, ...

def p_print_stmt(p):
    '''
    print_stmt : PRINT '*' ',' expr_list
    '''
    p[0] = ('print', p[4])

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
    p[0] = ('binop', p[2], p[1], p[3])

def p_expr_not(p):
    '''
    expr : NOT expr
    '''
    p[0] = ('unary', 'NOT', p[2])

def p_expr_uminus(p):
    '''
    expr : '-' expr %prec UMINUS
    '''
    p[0] = ('unary', '-', p[2])

def p_expr_group(p):
    '''
    expr : '(' expr ')'
    '''
    p[0] = p[2]

def p_expr_literals(p):
    '''
    expr : INTEGER_LIT
         | REAL_LIT
         | STRING_LIT
         | TRUE
         | FALSE
    '''
    t = p.slice[1].type
    if t == 'TRUE':
        p[0] = ('bool', True)
    elif t == 'FALSE':
        p[0] = ('bool', False)
    elif t == 'INTEGER_LIT':
        p[0] = ('int', p[1])
    elif t == 'REAL_LIT':
        p[0] = ('real', p[1])
    else:
        p[0] = ('str', p[1])

def p_expr_var(p):
    '''
    expr : ID
    '''
    p[0] = ('var', p[1])

# Covers both array element access (e.g. NUMS(I)) and function calls
# (e.g. CONVRT(N, B)). Disambiguated later in semantic analysis.
def p_expr_call_or_arr(p):
    '''
    expr : ID '(' expr_list ')'
    '''
    p[0] = ('call_or_arr', p[1], p[3])

# ── Error handler ─────────────────────────────────────────────────────────────

def p_error(p):
    if p:
        print(f"Syntax error at '{p.value}' (type: {p.type}) on line {p.lineno}")
    else:
        print("Syntax error: unexpected end of input")

# ── Build ─────────────────────────────────────────────────────────────────────

parser = yacc.yacc()
