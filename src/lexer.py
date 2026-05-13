# src/lexer.py
import ply.lex as lex

# ── Token list ───────────────────────────────────────────────────────────────
tokens = (
    # Keywords (handled inside t_ID)
    'PROGRAM', 'END',
    'INTEGER', 'REAL', 'LOGICAL', 'CHARACTER',
    'IF', 'THEN', 'ELSE', 'ENDIF',
    'DO', 'CONTINUE', 'GOTO',
    'READ', 'PRINT',
    'RETURN', 'FUNCTION', 'SUBROUTINE', 'CALL',

    # Multi-character arithmetic
    'POWER',

    # Relational operators
    'EQ', 'NE', 'LT', 'LE', 'GT', 'GE',

    # Logical operators
    'AND', 'OR', 'NOT',

    # Logical literals
    'TRUE', 'FALSE',

    # Value literals
    'INTEGER_LIT', 'REAL_LIT', 'STRING_LIT',

    # Identifier
    'ID',
)

# Single-character tokens — the type IS the character itself
literals = ['(', ')', ',', '=', '+', '-', '/', '*']

# ── Keyword dictionary ───────────────────────────────────────────────────────
KEYWORDS = {
    'PROGRAM'    : 'PROGRAM',
    'END'        : 'END',
    'INTEGER'    : 'INTEGER',
    'REAL'       : 'REAL',
    'LOGICAL'    : 'LOGICAL',
    'CHARACTER'  : 'CHARACTER',
    'IF'         : 'IF',
    'THEN'       : 'THEN',
    'ELSE'       : 'ELSE',
    'ENDIF'      : 'ENDIF',
    'DO'         : 'DO',
    'CONTINUE'   : 'CONTINUE',
    'GOTO'       : 'GOTO',
    'READ'       : 'READ',
    'PRINT'      : 'PRINT',
    'RETURN'     : 'RETURN',
    'FUNCTION'   : 'FUNCTION',
    'SUBROUTINE' : 'SUBROUTINE',
    'CALL'       : 'CALL',
}

# ── Multi-character arithmetic ───────────────────────────────────────────────
# Must be a function so PLY tests it before the '*' literal
def t_POWER(t):
    r'\*\*'
    return t

t_EQ = r'\.EQ\.'
t_NE = r'\.NE\.'
t_LE = r'\.LE\.'
t_LT = r'\.LT\.'
t_GE = r'\.GE\.'
t_GT = r'\.GT\.'
t_AND = r'\.AND\.'
t_OR  = r'\.OR\.'
t_NOT = r'\.NOT\.'
t_TRUE  = r'\.TRUE\.'
t_FALSE = r'\.FALSE\.'

# ── Value literals ───────────────────────────────────────────────────────────
def t_REAL_LIT(t):
    r'\d+\.\d*([Ee][+-]?\d+)?|\.\d+([Ee][+-]?\d+)?'
    t.value = float(t.value)
    return t

def t_INTEGER_LIT(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_STRING_LIT(t):
    r"'[^']*'"
    t.value = t.value[1:-1]  # strip surrounding quotes
    return t

# ── Identifiers and keywords ─────────────────────────────────────────────────
# Matches any identifier — then checks if it's actually a keyword
def t_ID(t):
    r'[A-Z][A-Z0-9]*'
    t.type  = KEYWORDS.get(t.value, 'ID')   # keyword or plain identifier
    return t

# ── Ignored characters ───────────────────────────────────────────────────────
t_ignore = ' \t'


# ── Error handling ───────────────────────────────────────────────────────────
def t_error(t):
    raise SyntaxError(f"Illegal character '{t.value[0]}' at line {t.lineno}")

# ── Build the lexer ──────────────────────────────────────────────────────────
lexer = lex.lex()

