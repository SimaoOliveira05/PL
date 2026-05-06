"""
AST node definitions for the Fortran 77 compiler.

Two phases share most of these classes:
  - The parser produces nodes with annotation fields (type, etc.) left as None.
  - The semantic analyser populates those fields and rewrites a few node
    classes that change shape (Do → DoLoop, CallOrArr → ArrRef|CallExpr).

Classes marked PARSER OUT exist only between parser and semantic.
Classes marked SEMANTIC OUT are produced by the semantic analyser and
consumed by IR generation.

Conventions:
  - Statement nodes inherit from Stmt and carry a `lineno` (kw-only) for
    error messages.
  - Expression nodes inherit from Expr.
  - Dataclasses are mutable; the semantic analyser populates `type` in place.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Union


# ── Base classes ─────────────────────────────────────────────────────────────

@dataclass
class Stmt:
    """Base class for all statement nodes."""
    lineno: Optional[int] = field(default=None, kw_only=True)


class Expr:
    """Base class for all expression nodes."""
    pass


# ── Program units ────────────────────────────────────────────────────────────

@dataclass
class Program(Stmt):
    """PROGRAM [name] ... END"""
    name: Optional[str]
    body: List[Stmt]


@dataclass
class Function(Stmt):
    """type FUNCTION name(params) ... END"""
    return_type: str
    name: str
    params: List[str]
    body: List[Stmt]


@dataclass
class Subroutine(Stmt):
    """SUBROUTINE name(params) ... END"""
    name: str
    params: List[str]
    body: List[Stmt]


# ── Declarators (sub-nodes of Decl) ──────────────────────────────────────────

@dataclass
class Scalar:
    """Plain variable declarator: A"""
    name: str


@dataclass
class Array:
    """Array declarator: A(5) or A(N).
    size is int for static arrays, str for dynamic arrays (size is a var name).
    """
    name: str
    size: Union[int, str]


# ── Statements (shared by parser and semantic) ───────────────────────────────

@dataclass
class Decl(Stmt):
    """INTEGER A, B(5), C(N)
    Stripped from the AST by the semantic analyser — the symbol table
    carries the same information from that point on.
    """
    type: str
    decls: List[Union[Scalar, Array]]


@dataclass
class Assign(Stmt):
    """LHS = RHS — LHS is Var or ArrRef."""
    lhs: Expr
    rhs: Expr


@dataclass
class If(Stmt):
    """IF (cond) THEN ... [ELSE ...] ENDIF"""
    cond: Expr
    then_body: List[Stmt]
    else_body: Optional[List[Stmt]]


@dataclass
class Goto(Stmt):
    label: int


@dataclass
class Continue(Stmt):
    pass


@dataclass
class Return(Stmt):
    pass


@dataclass
class Read(Stmt):
    """READ *, var, var, ..."""
    targets: List[Expr]


@dataclass
class Print(Stmt):
    """PRINT *, expr, expr, ..."""
    values: List[Expr]


@dataclass
class CallStmt(Stmt):
    """CALL name(args) — subroutine invocation."""
    name: str
    args: List[Expr]


@dataclass
class Labeled(Stmt):
    """Statement carrying a Fortran label (cols 1-5)."""
    label: int
    stmt: Stmt


# ── Statements: parser-only ──────────────────────────────────────────────────

@dataclass
class Do(Stmt):
    """PARSER OUT — flat DO header.

    The body is left loose in the surrounding stmt_list, terminated by a
    Labeled statement whose label matches `label`. The semantic analyser
    restructures these into DoLoop nodes with nested bodies.
    """
    label: int                 # terminal label
    var: str                   # iteration variable name (untyped at this point)
    start: Expr
    end: Expr
    step: Optional[Expr]       # None means "step omitted"; semantic applies default


# ── Statements: post-semantic ────────────────────────────────────────────────

@dataclass
class DoLoop(Stmt):
    """SEMANTIC OUT — restructured DO loop with nested body."""
    var: 'Var'                 # typed Var
    start: Expr
    end: Expr
    step: Expr                 # default already applied (typed correctly)
    body: List[Stmt]


# ── Expressions: literals ────────────────────────────────────────────────────

@dataclass
class IntLit(Expr):
    value: int
    type: str = 'INTEGER'


@dataclass
class RealLit(Expr):
    value: float
    type: str = 'REAL'


@dataclass
class StrLit(Expr):
    value: str
    type: str = 'CHARACTER'


@dataclass
class BoolLit(Expr):
    value: bool
    type: str = 'LOGICAL'


# ── Expressions: variables and composite (shared) ────────────────────────────

@dataclass
class Var(Expr):
    """Scalar variable reference.
    `type` is None until populated by the semantic analyser.
    """
    name: str
    type: Optional[str] = None


@dataclass
class ArrRef(Expr):
    """Indexed array reference: A(I).
    Used as lvalue (assignment target) and rvalue (expression).
    """
    name: str
    idx: Expr
    type: Optional[str] = None


@dataclass
class Binop(Expr):
    """Binary operation.

    pre-semantic:  op is the source operator string ('+', '.EQ.', '.AND.', '**')
    post-semantic: op is the VM opcode ('ADD', 'EQUAL', 'AND', 'POW') and
                   `type` holds the result type
    """
    op: str
    left: Expr
    right: Expr
    type: Optional[str] = None


@dataclass
class Unary(Expr):
    """Unary operation.

    pre-semantic:  op ∈ {'-', 'NOT'}
    post-semantic: op ∈ {'NEG', 'FNEG', 'NOT'} and `type` is set
    """
    op: str
    operand: Expr
    type: Optional[str] = None


# ── Expressions: parser-only ─────────────────────────────────────────────────

@dataclass
class CallOrArr(Expr):
    """PARSER OUT — ID(args) ambiguous between function call and array access.
    Resolved to ArrRef or CallExpr by the semantic analyser.
    """
    name: str
    args: List[Expr]


# ── Expressions: post-semantic ───────────────────────────────────────────────

@dataclass
class CallExpr(Expr):
    """SEMANTIC OUT — call to a function or intrinsic in expression position.
    Distinct from CallStmt (a Stmt used for subroutine calls).
    """
    name: str
    args: List[Expr]
    type: str                  # return type


@dataclass
class Coerce(Expr):
    """SEMANTIC OUT — implicit type coercion inserted by the semantic analyser.
    op is the VM opcode for the conversion (typically 'ITOF').
    """
    op: str
    src: Expr
    type: str                  # destination type
