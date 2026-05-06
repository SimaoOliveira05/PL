from ir import (
    INTRINSICS,
    KIND_SCALAR, KIND_ARRAY, KIND_DYN_ARRAY, KIND_PARAM, KIND_ARRAY_PARAM,
    KIND_FUNCTION, KIND_SUBROUTINE,
)
from ast_nodes import (
    Program, Function, Subroutine,
    Scalar, Array, Decl,
    Assign, If, Goto, Continue, Return, Read, Print,
    CallStmt, Labeled, Do, DoLoop,
    IntLit, RealLit, StrLit, BoolLit,
    Var, ArrRef, Binop, Unary, CallOrArr, CallExpr, Coerce,
)


class SemanticError(Exception):
    pass


_INT_OPS  = {'+': 'ADD',  '-': 'SUB',  '*': 'MUL',  '/': 'DIV'}
_REAL_OPS = {'+': 'FADD', '-': 'FSUB', '*': 'FMUL', '/': 'FDIV'}
_REL_INT  = {'.EQ.': 'EQUAL', '.NE.': 'NEQ', '.LT.': 'INF',  '.LE.': 'INFEQ', '.GT.': 'SUP',  '.GE.': 'SUPEQ'}
_REL_REAL = {'.EQ.': 'EQUAL', '.NE.': 'NEQ', '.LT.': 'FINF', '.LE.': 'FINFEQ','.GT.': 'FSUP', '.GE.': 'FSUPEQ'}


class SemanticAnalyser:

    # ── Setup ──────────────────────────────────────────────────────────────────

    def __init__(self):
        self.symtab = {}
        self.offset = 0
        self.labels = set()
        self.current_line = None
        self.signatures = {}    # name → {'kind': 'function'|'subroutine', 'arity': int}

    def error(self, message):
        line = f" (line {self.current_line})" if self.current_line else ""
        raise SemanticError(f'Semantic error{line}: {message}')

    def _resetScope(self):
        self.symtab = {}
        self.offset = 0
        self.labels = set()

    # ── Entry point ────────────────────────────────────────────────────────────

    def analyse(self, ast):
        # Pre-pass: collect signatures of all user-defined functions/subroutines
        # so calls can be validated regardless of declaration order.
        self.signatures = {}
        for unit in ast:
            if isinstance(unit, Function):
                self.signatures[unit.name] = {'kind': KIND_FUNCTION,   'arity': len(unit.params)}
            elif isinstance(unit, Subroutine):
                self.signatures[unit.name] = {'kind': KIND_SUBROUTINE, 'arity': len(unit.params)}
        return [self.analyseUnit(unit) for unit in ast]

    # ── Symbol table ───────────────────────────────────────────────────────────

    def addVariables(self, type_, decls):
        for d in decls:
            name = d.name

            if name in self.symtab:
                info = self.symtab[name]
                if info.get('kind') == KIND_PARAM and info['type'] is None:
                    info['type'] = type_
                    if isinstance(d, Array):
                        info['kind'] = KIND_ARRAY_PARAM
                        info['size'] = d.size
                    continue
                self.error(f"Duplicate variable declaration: '{name}'")

            if isinstance(d, Scalar):
                self.symtab[name] = {'type': type_, 'kind': KIND_SCALAR, 'offset': self.offset}
                self.offset += 1
            elif isinstance(d, Array):
                if isinstance(d.size, int):
                    self.symtab[name] = {'type': type_, 'kind': KIND_ARRAY, 'offset': self.offset, 'size': d.size}
                else:
                    self.symtab[name] = {'type': type_, 'kind': KIND_DYN_ARRAY, 'offset': self.offset, 'size': d.size}
                self.offset += 1

    def lookup(self, name):
        if name not in self.symtab:
            self.error(f'Undefined variable: {name}')
        return self.symtab[name]

    # ── Expression type checker ────────────────────────────────────────────────

    def checkType(self, expr, passed_as_arg=False):
        if isinstance(expr, (IntLit, RealLit, StrLit, BoolLit)):
            return expr

        if isinstance(expr, Var):
            info = self.lookup(expr.name)
            # passed_as_arg is True when called from a CallStmt or CallOrArr argument
            if info['kind'] in (KIND_ARRAY, KIND_DYN_ARRAY) and not passed_as_arg:
                self.error(f"Array '{expr.name}' used without index")
            return Var(name=expr.name, type=info['type'])

        if isinstance(expr, Binop):
            left_out  = self.checkType(expr.left)
            right_out = self.checkType(expr.right)
            ltype = left_out.type
            rtype = right_out.type

            if ltype != rtype:
                if {ltype, rtype} == {'INTEGER', 'REAL'}:
                    if ltype == 'INTEGER':
                        left_out = Coerce(op='ITOF', src=left_out, type='REAL')
                    else:
                        right_out = Coerce(op='ITOF', src=right_out, type='REAL')
                    result_type = 'REAL'
                else:
                    self.error(f'Type mismatch: {ltype} {expr.op} {rtype}')
            else:
                result_type = ltype

            op = expr.op
            if op in ('.EQ.', '.NE.', '.LT.', '.LE.', '.GT.', '.GE.'):
                table = _REL_REAL if result_type == 'REAL' else _REL_INT
                return Binop(op=table[op], left=left_out, right=right_out, type='LOGICAL')

            if op in ('.AND.', '.OR.'):
                if ltype != 'LOGICAL' or rtype != 'LOGICAL':
                    self.error(f"Logical operator {op} requires LOGICAL operands, got {ltype} and {rtype}")
                opcode = 'AND' if op == '.AND.' else 'OR'
                return Binop(op=opcode, left=left_out, right=right_out, type='LOGICAL')

            if op == '**':
                opcode = 'FPOW' if result_type == 'REAL' else 'POW'
                return Binop(op=opcode, left=left_out, right=right_out, type=result_type)

            opcode = _REAL_OPS[op] if result_type == 'REAL' else _INT_OPS[op]
            return Binop(op=opcode, left=left_out, right=right_out, type=result_type)

        if isinstance(expr, Unary):
            operand_out = self.checkType(expr.operand)
            otype = operand_out.type
            if expr.op == '-':
                if otype not in ('INTEGER', 'REAL'):
                    self.error(f"Unary minus requires numeric operand, got {otype}")
                return Unary(op='-', operand=operand_out, type=otype)
            if expr.op == 'NOT':
                if otype != 'LOGICAL':
                    self.error(f".NOT. requires LOGICAL operand, got {otype}")
                return Unary(op='NOT', operand=operand_out, type='LOGICAL')
            self.error(f"Unknown unary operator: {expr.op}")

        if isinstance(expr, CallOrArr):
            args_out = [self.checkType(a, passed_as_arg=True) for a in expr.args]
            if expr.name in INTRINSICS:
                ret = INTRINSICS[expr.name][0]
                if ret == 'SAME':
                    ret = args_out[0].type
                return CallExpr(name=expr.name, args=args_out, type=ret)
            info = self.lookup(expr.name)
            if info['kind'] in (KIND_ARRAY, KIND_ARRAY_PARAM, KIND_DYN_ARRAY):
                if len(args_out) != 1:
                    self.error(f"Array '{expr.name}' indexed with {len(args_out)} indices")
                return ArrRef(name=expr.name, idx=args_out[0], type=info['type'])
            sig = self.signatures.get(expr.name)
            if sig is not None and sig['kind'] == KIND_FUNCTION and len(args_out) != sig['arity']:
                self.error(f"Function '{expr.name}' expects {sig['arity']} argument(s), got {len(args_out)}")
            return CallExpr(name=expr.name, args=args_out, type=info['type'])

        if isinstance(expr, ArrRef):
            info = self.lookup(expr.name)
            idx_out = self.checkType(expr.idx)
            return ArrRef(name=expr.name, idx=idx_out, type=info['type'])

        self.error(f'Unknown expression type: {type(expr).__name__}')

    # ── Statement checker ──────────────────────────────────────────────────────

    def checkStmt(self, stmt):
        if isinstance(stmt, Decl):
            self.addVariables(stmt.type, stmt.decls)
            return None  # stripped from output

        if isinstance(stmt, Assign):
            lout = self.checkType(stmt.lhs)
            rout = self.checkType(stmt.rhs)
            ltype = lout.type
            rtype = rout.type
            if ltype != rtype:
                if ltype == 'REAL' and rtype == 'INTEGER':
                    rout = Coerce(op='ITOF', src=rout, type='REAL')
                else:
                    self.error(f'Type mismatch: {ltype} = {rtype}')
            return Assign(lhs=lout, rhs=rout, lineno=stmt.lineno)

        if isinstance(stmt, Read):
            return Read(targets=[self.checkType(v) for v in stmt.targets], lineno=stmt.lineno)

        if isinstance(stmt, Print):
            return Print(values=[self.checkType(v) for v in stmt.values], lineno=stmt.lineno)

        if isinstance(stmt, If):
            cond_out = self.checkType(stmt.cond)
            then_out = [r for r in (self.checkStmt(s) for s in stmt.then_body) if r is not None]
            else_out = None
            if stmt.else_body is not None:
                else_out = [r for r in (self.checkStmt(s) for s in stmt.else_body) if r is not None]
            return If(cond=cond_out, then_body=then_out, else_body=else_out, lineno=stmt.lineno)

        if isinstance(stmt, Goto):
            if stmt.label not in self.labels:
                self.error(f"GOTO references undefined label {stmt.label}")
            return Goto(label=stmt.label, lineno=stmt.lineno)

        if isinstance(stmt, Continue):
            return Continue(lineno=stmt.lineno)

        if isinstance(stmt, Return):
            return Return(lineno=stmt.lineno)

        if isinstance(stmt, CallStmt):
            args_out = [self.checkType(a, passed_as_arg=True) for a in stmt.args]
            sig = self.signatures.get(stmt.name)
            if sig is None:
                self.error(f"CALL to undefined subroutine '{stmt.name}'")
            if sig['kind'] != KIND_SUBROUTINE:
                self.error(f"'{stmt.name}' is a function, cannot be invoked with CALL")
            if len(args_out) != sig['arity']:
                self.error(f"Subroutine '{stmt.name}' expects {sig['arity']} argument(s), got {len(args_out)}")
            return CallStmt(name=stmt.name, args=args_out, lineno=stmt.lineno)

        if isinstance(stmt, Labeled):
            inner_out = self.checkStmt(stmt.stmt)
            if inner_out is None:
                return None
            return Labeled(label=stmt.label, stmt=inner_out, lineno=stmt.lineno)

        if isinstance(stmt, Do):
            self.error("DO loops nested inside other constructs (e.g. IF) are not supported")

        self.error(f'Unknown statement type: {type(stmt).__name__}')

    # ── AST traversal ─────────────────────────────────────────────────────────

    def analyseStmts(self, stmts):
        output   = []
        do_stack = []   # each frame: [terminal_label, var, start, end, step, body]

        # scan for labels first so forward references (GOTO, DO) work
        for stmt in stmts:
            if isinstance(stmt, Labeled):
                self.labels.add(stmt.label)

        for stmt in stmts:
            self.current_line = stmt.lineno

            if isinstance(stmt, Decl):
                self.checkStmt(stmt)   # registers in symtab; no AST output
                continue

            if isinstance(stmt, Do):
                if stmt.label not in self.labels:
                    self.error(f"DO references undefined label {stmt.label}")
                var_out   = self.checkType(Var(name=stmt.var))
                var_type  = var_out.type
                start_out = self.checkType(stmt.start)
                end_out   = self.checkType(stmt.end)
                if stmt.step is not None:
                    step_out = self.checkType(stmt.step)
                elif var_type == 'REAL':
                    step_out = RealLit(value=1.0)
                else:
                    step_out = IntLit(value=1)
                do_stack.append([stmt.label, var_out, start_out, end_out, step_out, []])
                continue

            if isinstance(stmt, Labeled):
                inner = stmt.stmt
                if isinstance(inner, Continue) and do_stack and do_stack[-1][0] == stmt.label:
                    # close all DO loops sharing this terminal label
                    while do_stack and do_stack[-1][0] == stmt.label:
                        frame = do_stack.pop()
                        loop = DoLoop(
                            var=frame[1], start=frame[2], end=frame[3],
                            step=frame[4], body=frame[5], lineno=stmt.lineno,
                        )
                        dest = do_stack[-1][5] if do_stack else output
                        dest.append(loop)
                else:
                    out = self.checkStmt(stmt)
                    if out is not None:
                        dest = do_stack[-1][5] if do_stack else output
                        dest.append(out)
                continue

            out = self.checkStmt(stmt)
            if out is not None:
                dest = do_stack[-1][5] if do_stack else output
                dest.append(out)

        if do_stack:
            self.error(f"DO loop with label {do_stack[-1][0]} was never terminated")

        return output

    def analyseUnit(self, unit):
        if isinstance(unit, Program):
            self._resetScope()
            new_body = self.analyseStmts(unit.body)
            return Program(name=unit.name, body=new_body, lineno=unit.lineno), self.symtab

        if isinstance(unit, Function):
            self._resetScope()
            # the function name is a hidden local at offset 0 (used to set the return value)
            self.symtab[unit.name] = {'type': unit.return_type, 'kind': KIND_SCALAR, 'offset': self.offset}
            self.offset += 1
            for pname in unit.params:
                self.symtab[pname] = {'type': None, 'kind': KIND_PARAM, 'offset': self.offset}
                self.offset += 1
            new_body = self.analyseStmts(unit.body)
            return Function(
                return_type=unit.return_type, name=unit.name,
                params=unit.params, body=new_body, lineno=unit.lineno,
            ), self.symtab

        if isinstance(unit, Subroutine):
            self._resetScope()
            for pname in unit.params:
                self.symtab[pname] = {'type': None, 'kind': KIND_PARAM , 'offset': self.offset}
                self.offset += 1
            new_body = self.analyseStmts(unit.body)
            return Subroutine(
                name=unit.name, params=unit.params,
                body=new_body, lineno=unit.lineno,
            ), self.symtab

        self.error(f'Unknown program unit type: {type(unit).__name__}')
