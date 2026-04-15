# src/semantic.py
"""
Semantic analyser for Fortran 77.

Takes an AST (list of program units) produced by the parser and returns an
annotated AST plus a symbol table.


Annotated node shapes (type is always appended as last element for
literal/op nodes; var/arr_ref carry (name, type, offset) so type is [-2]):

  ('int',     v,              'INTEGER')
  ('real',    v,              'REAL')
  ('str',     v,              'CHARACTER')
  ('bool',    v,              'LOGICAL')
  ('var',     name, type,     offset)
  ('arr_ref', name, idx_out,  type, offset)
  ('binop',   op,   l, r,     type)
  ('unary',   op,   e,        type)
  ('coerce',  'ITOF', e,      'REAL')
  ('do_loop', var, start, end, step, body)   ← restructured DO loop
"""


class SemanticError(Exception):
    pass


# Operator classification (matches token values produced by the lexer/parser)
_ARITH_OPS     = {'+', '-', '*', '/', '**'}
_RELATIONAL_OPS = {'.EQ.', '.NE.', '.LT.', '.LE.', '.GT.', '.GE.'}
_LOGICAL_OPS   = {'.AND.', '.OR.'}
_NUMERIC       = {'INTEGER', 'REAL'}

# Fortran 77 intrinsic functions: name → callable(argtypes) → return_type
# argtypes is a list of inferred types for the call arguments.
_INTRINSICS = {
    'MOD':   lambda ts: ts[0] if ts else 'INTEGER',
    'ABS':   lambda ts: ts[0] if ts else 'REAL',
    'SQRT':  lambda ts: 'REAL',
    'INT':   lambda ts: 'INTEGER',
    'REAL':  lambda ts: 'REAL',
    'FLOAT': lambda ts: 'REAL',
    'MAX':   lambda ts: ts[0] if ts else 'REAL',
    'MIN':   lambda ts: ts[0] if ts else 'REAL',
    'MAX0':  lambda ts: 'INTEGER',
    'MIN0':  lambda ts: 'INTEGER',
    'MAX1':  lambda ts: 'REAL',
    'MIN1':  lambda ts: 'REAL',
}

# Fortran implicit typing: names starting with I–N are INTEGER, else REAL.
_INTEGER_INITIALS = set('IJKLMN')


def _implicit_type(name: str) -> str:
    return 'INTEGER' if name[0].upper() in _INTEGER_INITIALS else 'REAL'


def _expr_type(node):
    """Extract the inferred type from an annotated expression node."""
    tag = node[0]
    if tag in ('var', 'arr_ref'):
        return node[-2]   # (name, ..., type, offset)
    return node[-1]       # type is always the last field for other nodes


class SemanticAnalyser:

    def __init__(self):
        self.symtab = {}              # name → {type, kind, offset, ?size}
        self._next_offset = 0
        self._labels = set()          # all labels in current program unit
        self._label_stmts = {}        # label → inner-stmt tag (for DO validation)
        self._declarations_closed = False

    # ── Public error hook ──────────────────────────────────────────────────────

    def error(self, msg: str):
        """Raise a SemanticError.  Change to collect-all later if desired."""
        raise SemanticError(msg)

    # ── Entry point ────────────────────────────────────────────────────────────

    def analyse(self, ast):
        """
        ast : list of program-unit tuples (parser output).
        Returns the annotated AST (same list structure).
        """
        return [self._analyse_unit(unit) for unit in ast]

    # ── Program unit ───────────────────────────────────────────────────────────

    def _analyse_unit(self, unit):
        tag = unit[0]
        if tag == 'program':
            _, name, stmts = unit
            self._reset()
            self._labels, self._label_stmts = self._collect_labels(stmts)
            new_stmts = self._analyse_stmts(stmts)
            return ('program', name, new_stmts)
        # Subprograms are out of scope — pass through unchanged.
        return unit

    def _reset(self):
        self.symtab = {}
        self._next_offset = 0
        self._labels = set()
        self._label_stmts = {}
        self._declarations_closed = False

    # ── Scan 1: label collection ───────────────────────────────────────────────

    def _collect_labels(self, stmts, labels=None, label_stmts=None):
        """
        Walk a stmt list (and nested IF bodies) to collect:
        labels      — set of all label numbers
        label_stmts — dict label → inner-stmt tag
        Raises on duplicate labels.
        """
        if labels is None:
            labels = set()
            label_stmts = {}

        for stmt in stmts:
            if stmt[0] == 'labeled':
                _, lbl, inner = stmt
                if lbl in labels:
                    self.error(f"Duplicate label {lbl}")
                labels.add(lbl)
                label_stmts[lbl] = inner[0]
                node = inner
            else:
                node = stmt

            if node[0] == 'if':
                _, _cond, then_stmts, else_stmts = node
                self._collect_labels(then_stmts, labels, label_stmts)
                if else_stmts:
                    self._collect_labels(else_stmts, labels, label_stmts)

        return labels, label_stmts

    # ── Scan 2: main pass ──────────────────────────────────────────────────────

    def _analyse_stmts(self, stmts):
        """
        Walk a flat statement list, restructuring DO loops from flat to nested.

        DO stack frames:  [label, var, start_out, end_out, step_out, body_list]
        """
        output = []
        do_stack = []

        for stmt in stmts:
            tag = stmt[0]

            # ── Labeled statement ─────────────────────────────────────────────
            if tag == 'labeled':
                _, lbl, inner = stmt

                if inner[0] == 'continue':
                    # Does this CONTINUE close the innermost open DO?
                    if do_stack and do_stack[-1][0] == lbl:
                        frame = do_stack.pop()
                        do_loop = ('do_loop',
                                   frame[1],   # var
                                   frame[2],   # start
                                   frame[3],   # end
                                   frame[4],   # step (None → default 1)
                                   frame[5])   # body
                        dest = do_stack[-1][5] if do_stack else output
                        dest.append(do_loop)
                    else:
                        # Labeled CONTINUE not matching any DO (e.g. GOTO target)
                        dest = do_stack[-1][5] if do_stack else output
                        dest.append(('labeled', lbl, ('continue',)))
                    continue

                # Non-CONTINUE labeled statement
                processed = self._check_stmt(inner)
                dest = do_stack[-1][5] if do_stack else output
                dest.append(('labeled', lbl, processed))
                continue

            # ── DO header ────────────────────────────────────────────────────
            if tag == 'do':
                self._declarations_closed = True
                _, lbl, var, start, end, step = stmt

                if lbl not in self._labels:
                    self.error(f"DO references undefined label {lbl}")
                if self._label_stmts.get(lbl) != 'continue':
                    self.error(
                        f"DO label {lbl} does not point to a CONTINUE statement")
                if var not in self.symtab:
                    self.error(f"Undeclared DO loop variable: {var}")
                vinfo = self.symtab[var]
                if vinfo['type'] not in _NUMERIC:
                    self.error(f"DO loop variable '{var}' must be numeric")

                start_out = self.check_expr(start)
                if _expr_type(start_out) not in _NUMERIC:
                    self.error("DO loop start bound must be numeric")
                end_out = self.check_expr(end)
                if _expr_type(end_out) not in _NUMERIC:
                    self.error("DO loop end bound must be numeric")
                if step is not None:
                    step_out = self.check_expr(step)
                    if _expr_type(step_out) not in _NUMERIC:
                        self.error("DO loop step must be numeric")
                else:
                    step_out = None

                do_stack.append([lbl, var, start_out, end_out, step_out, []])
                continue

            # ── All other statements ──────────────────────────────────────────
            processed = self._check_stmt(stmt)
            dest = do_stack[-1][5] if do_stack else output
            dest.append(processed)

        if do_stack:
            lbl = do_stack[-1][0]
            self.error(
                f"DO loop with label {lbl} was never terminated (missing CONTINUE)")

        return output

    # ── Statement checker ──────────────────────────────────────────────────────

    def _check_stmt(self, stmt):
        """Check a single (unlabeled) statement; returns the annotated node."""
        tag = stmt[0]

        # ── Declaration ───────────────────────────────────────────────────────
        if tag == 'decl':
            if self._declarations_closed:
                self.error("Declaration after executable statement")
            _, type_str, var_decls = stmt
            new_decls = [self._add_var(type_str, vd) for vd in var_decls]
            return ('decl', type_str, new_decls)

        # Everything below is executable → lock declaration section.
        self._declarations_closed = True

        # ── Assignment ────────────────────────────────────────────────────────
        if tag == 'assign':
            return self._check_assign(stmt)

        # ── IF ────────────────────────────────────────────────────────────────
        if tag == 'if':
            _, cond, then_stmts, else_stmts = stmt
            cond_out = self.check_expr(cond)
            if _expr_type(cond_out) != 'LOGICAL':
                self.error(
                    f"IF condition must be LOGICAL, got {_expr_type(cond_out)}")
            then_out = self._analyse_stmts(then_stmts)
            else_out = self._analyse_stmts(else_stmts) if else_stmts else None
            return ('if', cond_out, then_out, else_out)

        # ── GOTO ──────────────────────────────────────────────────────────────
        if tag == 'goto':
            _, lbl = stmt
            if lbl not in self._labels:
                self.error(f"GOTO references undefined label {lbl}")
            return stmt

        # ── PRINT ─────────────────────────────────────────────────────────────
        if tag == 'print':
            _, exprs = stmt
            return ('print', [self.check_expr(e) for e in exprs])

        # ── READ ──────────────────────────────────────────────────────────────
        if tag == 'read':
            _, lvalues = stmt
            return ('read', [self._check_lvalue(lv) for lv in lvalues])

        # ── Pass-through: CONTINUE, RETURN, CALL ─────────────────────────────
        if tag in ('continue', 'return', 'call'):
            return stmt

        self.error(f"Unknown statement tag: '{tag}'")

    # ── Variable declaration ───────────────────────────────────────────────────

    def _add_var(self, type_str, vd):
        vtag = vd[0]
        if vtag == 'scalar':
            _, name = vd
            if name in self.symtab:
                self.error(f"Duplicate variable declaration: '{name}'")
            off = self._next_offset
            self._next_offset += 1
            self.symtab[name] = {'type': type_str, 'kind': 'scalar', 'offset': off}
            return ('scalar', name)
        if vtag == 'array':
            _, name, size = vd
            if name in self.symtab:
                self.error(f"Duplicate variable declaration: '{name}'")
            off = self._next_offset
            self._next_offset += 1
            self.symtab[name] = {
                'type': type_str, 'kind': 'array', 'offset': off, 'size': size}
            return ('array', name, size)
        self.error(f"Unknown var_decl tag: '{vtag}'")

    # ── Assignment ─────────────────────────────────────────────────────────────

    def _check_assign(self, stmt):
        _, lhs, rhs = stmt
        ltag = lhs[0]

        if ltag == 'var':
            name = lhs[1]
            info = self._lookup(name)
            if info['kind'] == 'array':
                self.error(f"Array '{name}' used without index on left-hand side")
            ltype = info['type']
            new_lhs = ('var', name, ltype, info['offset'])

        elif ltag == 'arr_ref':
            name, idx = lhs[1], lhs[2]
            info = self._lookup(name)
            if info['kind'] == 'scalar':
                self.error(f"Scalar '{name}' used with index on left-hand side")
            idx_out = self.check_expr(idx)
            if _expr_type(idx_out) != 'INTEGER':
                self.error(f"Array index for '{name}' must be INTEGER")
            self._check_static_bounds(name, info, idx_out)
            ltype = info['type']
            new_lhs = ('arr_ref', name, idx_out, ltype, info['offset'])

        else:
            self.error(f"Unknown lvalue tag: '{ltag}'")

        rhs_out = self.check_expr(rhs)
        rtype = _expr_type(rhs_out)

        if ltype == rtype:
            pass  # exact match — no coercion
        elif ltype == 'REAL' and rtype == 'INTEGER':
            rhs_out = ('coerce', 'ITOF', rhs_out, 'REAL')
        else:
            self.error(
                f"Type mismatch in assignment: cannot assign {rtype} to {ltype}")

        return ('assign', new_lhs, rhs_out)

    # ── READ lvalue ────────────────────────────────────────────────────────────

    def _check_lvalue(self, lv):
        ltag = lv[0]
        if ltag == 'var':
            name = lv[1]
            info = self._lookup(name)
            return ('var', name, info['type'], info['offset'])
        if ltag == 'arr_ref':
            name, idx = lv[1], lv[2]
            info = self._lookup(name)
            if info['kind'] == 'scalar':
                self.error(f"Scalar '{name}' used with index in READ")
            idx_out = self.check_expr(idx)
            if _expr_type(idx_out) != 'INTEGER':
                self.error(f"Array index for '{name}' must be INTEGER")
            self._check_static_bounds(name, info, idx_out)
            return ('arr_ref', name, idx_out, info['type'], info['offset'])
        self.error(f"Unknown lvalue tag in READ: '{ltag}'")

    # ── Expression type checker ────────────────────────────────────────────────

    def check_expr(self, expr):
        """
        Recursively type-checks and annotates an expression node.
        Returns the annotated node; the inferred type is accessible via
        _expr_type(node).
        """
        tag = expr[0]

        if tag == 'int':
            return ('int', expr[1], 'INTEGER')

        if tag == 'real':
            return ('real', expr[1], 'REAL')

        if tag == 'str':
            return ('str', expr[1], 'CHARACTER')

        if tag == 'bool':
            return ('bool', expr[1], 'LOGICAL')

        if tag == 'var':
            name = expr[1]
            info = self._lookup(name)
            if info['kind'] == 'array':
                self.error(f"Array '{name}' used without index in expression")
            return ('var', name, info['type'], info['offset'])

        if tag == 'arr_ref':
            name, idx = expr[1], expr[2]
            info = self._lookup(name)
            if info['kind'] == 'scalar':
                self.error(f"Scalar '{name}' used with index in expression")
            idx_out = self.check_expr(idx)
            if _expr_type(idx_out) != 'INTEGER':
                self.error(f"Array index for '{name}' must be INTEGER")
            self._check_static_bounds(name, info, idx_out)
            return ('arr_ref', name, idx_out, info['type'], info['offset'])

        if tag == 'call_or_arr':
            name, args = expr[1], expr[2]
            args_out = [self.check_expr(a) for a in args]
            argtypes  = [_expr_type(a) for a in args_out]

            # ── Try to resolve as array element ──────────────────────────────
            if name in self.symtab and self.symtab[name]['kind'] == 'array':
                info = self.symtab[name]
                if len(args_out) != 1:
                    self.error(
                        f"Array '{name}' must be subscripted with exactly one index")
                idx_out = args_out[0]
                if _expr_type(idx_out) != 'INTEGER':
                    self.error(f"Array index for '{name}' must be INTEGER")
                self._check_static_bounds(name, info, idx_out)
                return ('arr_ref', name, idx_out, info['type'], info['offset'])

            # ── Treat as function call ────────────────────────────────────────
            # Determine return type: symtab declaration > intrinsics > implicit
            if name in self.symtab:
                ret_type = self.symtab[name]['type']   # e.g. INTEGER CONVRT
            elif name in _INTRINSICS:
                ret_type = _INTRINSICS[name](argtypes)
            else:
                ret_type = _implicit_type(name)        # Fortran implicit typing

            return ('func_call', name, args_out, ret_type)

        if tag == 'binop':
            _, op, left, right = expr
            left_out  = self.check_expr(left)
            right_out = self.check_expr(right)
            ltype = _expr_type(left_out)
            rtype = _expr_type(right_out)

            if op in _ARITH_OPS:
                if ltype not in _NUMERIC or rtype not in _NUMERIC:
                    self.error(
                        f"Operator '{op}' requires numeric operands, "
                        f"got {ltype} and {rtype}")
                if 'REAL' in (ltype, rtype):
                    if ltype == 'INTEGER':
                        left_out = ('coerce', 'ITOF', left_out, 'REAL')
                    if rtype == 'INTEGER':
                        right_out = ('coerce', 'ITOF', right_out, 'REAL')
                    result_type = 'REAL'
                else:
                    result_type = 'INTEGER'
                return ('binop', op, left_out, right_out, result_type)

            if op in _RELATIONAL_OPS:
                if ltype not in _NUMERIC or rtype not in _NUMERIC:
                    self.error(
                        f"Relational operator '{op}' requires numeric operands, "
                        f"got {ltype} and {rtype}")
                if 'REAL' in (ltype, rtype):
                    if ltype == 'INTEGER':
                        left_out = ('coerce', 'ITOF', left_out, 'REAL')
                    if rtype == 'INTEGER':
                        right_out = ('coerce', 'ITOF', right_out, 'REAL')
                return ('binop', op, left_out, right_out, 'LOGICAL')

            if op in _LOGICAL_OPS:
                if ltype != 'LOGICAL' or rtype != 'LOGICAL':
                    self.error(
                        f"Logical operator '{op}' requires LOGICAL operands, "
                        f"got {ltype} and {rtype}")
                return ('binop', op, left_out, right_out, 'LOGICAL')

            self.error(f"Unknown binary operator: '{op}'")

        if tag == 'unary':
            _, op, operand = expr
            operand_out = self.check_expr(operand)
            otype = _expr_type(operand_out)
            if op == '-':
                if otype not in _NUMERIC:
                    self.error(
                        f"Unary minus requires numeric operand, got {otype}")
                return ('unary', '-', operand_out, otype)
            if op == 'NOT':
                if otype != 'LOGICAL':
                    self.error(f".NOT. requires LOGICAL operand, got {otype}")
                return ('unary', 'NOT', operand_out, 'LOGICAL')
            self.error(f"Unknown unary operator: '{op}'")

        if tag == 'coerce':
            # Already annotated (e.g. when re-checking a pre-annotated tree)
            return expr

        self.error(f"Unknown expression tag: '{tag}'")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _lookup(self, name):
        if name not in self.symtab:
            self.error(f"Undeclared variable: '{name}'")
        return self.symtab[name]

    def _check_static_bounds(self, name, info, idx_node):
        """If idx_node is a compile-time integer literal, check 1 ≤ idx ≤ size."""
        if idx_node[0] == 'int':
            n = idx_node[1]
            size = info['size']
            if not (1 <= n <= size):
                self.error(
                    f"Array '{name}': index {n} out of bounds "
                    f"(valid range 1–{size})")


# ── Convenience wrapper ────────────────────────────────────────────────────────

def analyse(ast):
    """
    Run semantic analysis on a parsed AST.

    Returns (annotated_ast, symbol_table).
    symbol_table is the table of the *last* analysed program unit (sufficient
    for single-program files).
    """
    sa = SemanticAnalyser()
    annotated = sa.analyse(ast)
    return annotated, sa.symtab
