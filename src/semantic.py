
from ir import INTRINSICS as _INTRINSICS

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

    def error(self, message):
        line = f" (line {self.current_line})" if self.current_line else ""
        raise Exception(f'Semantic error{line}: {message}')

    # ── Entry point ────────────────────────────────────────────────────────────

    def analyse(self, ast):
        result = []
        for unit in ast:
            result.append(self.analyseUnit(unit))
        return result

    # ── Symbol table ───────────────────────────────────────────────────────────

    def addVariables(self, type, names):
        for var in names:
            vtag = var[0]
            name = var[1]

            if name in self.symtab:
                info = self.symtab[name]
                if info.get('kind') == 'param' and info['type'] is None:
                    info['type'] = type
                    if vtag == "array":
                        info['kind'] = 'array_param' #Precisamos de declarar que é um array como parametro
                        info['size'] = var[2]
                    continue
                self.error(f"Duplicate variable declaration: '{name}'")

            if vtag == 'scalar':
                self.symtab[name] = {'type': type, 'kind': 'scalar', 'offset': self.offset}
                self.offset += 1
            elif vtag == 'array':
                size = var[2]
                if isinstance(size,int):
                    self.symtab[name] = {'type': type, 'kind': 'array', 'offset': self.offset, 'size': size}
                else:
                    self.symtab[name] = {'type': type, 'kind': 'dynamic-array', 'offset': self.offset, 'size': size}
                self.offset += 1 #we use struct heap now so only need 1 slot in stack



    def lookup(self, name):
        if name not in self.symtab:
            self.error(f'Undefined variable: {name}')
        return self.symtab[name]

    # ── Type helpers ───────────────────────────────────────────────────────────

    def getType(self, node):
        tag = node[0]
        if tag == 'var':
            return node[2]       # ('var', name, type, offset)
        if tag == 'arr_ref':
            return node[3]       # ('arr_ref', name, idx, type, offset)
        return node[-1]          # type is last for everything else

    # ── Expression type checker ────────────────────────────────────────────────

    def checkType(self, expr, passed_as_arg=False):
        
        tag = expr[0]

        if tag == 'var':
            name = expr[1]
            info = self.lookup(name)
            #Passed as arg é colcoado a TRUE por call e por call_or_arr
            if info['kind'] in ('array', 'dynamic_array') and not passed_as_arg:
                self.error(f"Array '{name}' used without index")
            return ('var', name, info['type'], info['offset'])

        if tag == 'int':
            return ('int', expr[1], 'INTEGER')

        if tag == 'real':
            return ('real', expr[1], 'REAL')

        if tag == 'bool':
            return ('bool', expr[1], 'LOGICAL')

        if tag == 'str':
            return ('str', expr[1], 'CHARACTER')

        if tag == 'binop':
            _, op, left, right = expr
            left_out  = self.checkType(left)
            right_out = self.checkType(right)
            ltype = self.getType(left_out)
            rtype = self.getType(right_out)
            if ltype != rtype:
                if {ltype, rtype} == {'INTEGER', 'REAL'}:
                    if ltype == 'INTEGER':
                        left_out = ('coerce', 'ITOF', left_out, 'REAL')
                    else:
                        right_out = ('coerce', 'ITOF', right_out, 'REAL')
                    result_type = 'REAL'
                else:
                    self.error(f'Type mismatch: {ltype} {op} {rtype}')
            else:
                result_type = ltype

            if op in ('.EQ.', '.NE.', '.LT.', '.LE.', '.GT.', '.GE.'):
                table = _REL_REAL if result_type == 'REAL' else _REL_INT
                opcode = table[op]
                return ('binop', opcode, left_out, right_out, 'LOGICAL')

            if op in ('.AND.', '.OR.'):
                if ltype != 'LOGICAL' or rtype != 'LOGICAL':
                    self.error(f"Logical operator {op} requires LOGICAL operands, got {ltype} and {rtype}")
                opcode = 'AND' if op == '.AND.' else 'OR'
                return ('binop', opcode, left_out, right_out, 'LOGICAL')

            if op == '**':
                opcode = 'FPOW' if result_type == 'REAL' else 'POW'
                return ('binop', opcode, left_out, right_out, result_type)

            opcode = _REAL_OPS[op] if result_type == 'REAL' else _INT_OPS[op]
            return ('binop', opcode, left_out, right_out, result_type)


        if tag == 'unary':
            _, op, operand = expr
            operand_out = self.checkType(operand)
            otype = self.getType(operand_out)

            if op == '-':
                if otype not in ('INTEGER', 'REAL'):
                    self.error(f"Unary minus requires numeric operand, got {otype}")
                return ('unary', op, operand_out, otype)
            
            if op == 'NOT':
                if otype != 'LOGICAL':
                    self.error(f".NOT. requires LOGICAL operand, got {otype}")
                return ('unary', op, operand_out, 'LOGICAL')
            
            self.error(f"Unknown unary operator: {op}")

        if tag == 'call_or_arr':
            name = expr[1]
            args = expr[2]
            args_out = [self.checkType(arg, passed_as_arg=True) for arg in args]
            if name in _INTRINSICS:
                ret = _INTRINSICS[name][0]
                if ret == 'SAME':
                    ret = self.getType(args_out[0])
                return ('call', name, args_out, ret)
            info = self.lookup(name)
            if info['kind'] in ('array', 'array_param'):
                if len(args_out) != 1:
                    self.error(f"Array '{name}' indexed with {len(args_out)} indices")
                return ('arr_ref', name, args_out[0], info['type'], info['offset'])
            return ('call', name, args_out, info['type'])

        if tag == 'arr_ref':
            name = expr[1]
            idx  = expr[2]
            info = self.lookup(name)
            idx_out = self.checkType(idx)
            return ('arr_ref', name, idx_out, info['type'], info['offset'])

        self.error(f'Unknown expression tag: {tag}')

    # ── Statement checker ──────────────────────────────────────────────────────

    def checkStmt(self, stmt):
        tag = stmt[0]

        if tag == 'decl':
            self.addVariables(stmt[1], stmt[2])
            return stmt

        if tag == 'assign':
            _, lhs, rhs = stmt
            lout  = self.checkType(lhs)
            rout  = self.checkType(rhs)
            ltype = self.getType(lout)
            rtype = self.getType(rout)
            if ltype == rtype:
                pass
            elif ltype == 'REAL' and rtype == 'INTEGER':
                # implicit INTEGER → REAL coercion
                rout = ('coerce', 'ITOF', rout, 'REAL')
            else:
                self.error(f'Type mismatch: {ltype} = {rtype}')
            return ('assign', lout, rout)

        if tag == 'read':
            _, variables = stmt
            return ('read', [self.checkType(v) for v in variables])

        if tag == 'print':
            _, variables = stmt
            return ('print', [self.checkType(v) for v in variables])

        if tag == 'do':
            _, terminal_label, loop_variable, start, end, step = stmt
            var_out   = self.checkType(('var', loop_variable))
            start_out = self.checkType(start)
            end_out   = self.checkType(end)
            step_out  = self.checkType(step) if step is not None else ('int', 1, 'INTEGER')
            if terminal_label not in self.labels:
                self.error(f"DO references undefined label {terminal_label}")
            return ('do', terminal_label, var_out, start_out, end_out, step_out)

        if tag == 'labeled':
            _, label, inner = stmt
            if inner[0] == 'continue':
                return ('labeled', label, ('continue',))
            return ('labeled', label, self.checkStmt(inner))

        if tag == 'if':
            _, condition, then_stmts, else_stmts = stmt
            cond_out = self.checkType(condition)
            then_out = [self._check(s) for s in then_stmts]
            else_out = [self._check(s) for s in else_stmts] if else_stmts else None
            return ('if', cond_out, then_out, else_out)

        if tag == 'goto':
            _, label = stmt
            if label not in self.labels:
                self.error(f"GOTO references undefined label {label}")
            return ('goto', label)

        if tag == 'continue':
            return ('continue',)

        if tag == 'return':
            return ('return',)

        if tag == 'call':
            _, name, args = stmt
            return ('call', name, [self.checkType(a,passed_as_arg=True) for a in args])

    # ── AST traversal ─────────────────────────────────────────────────────────

    def _check(self, stmt_with_line):
        node, lineno = stmt_with_line
        self.current_line = lineno
        return self.checkStmt(node)

    def analyseStmts(self, stmts):
        output   = []
        do_stack = []

        # scan for labels first so forward references (GOTO, DO) work
        for node, lineno in stmts:
            if node[0] == 'labeled':
                _, label, inner = node
                self.labels.add(label)

        for node, lineno in stmts:
            self.current_line = lineno
            tag = node[0]

            if tag not in ('labeled', 'do'):
                out  = self.checkStmt(node)
                dest = do_stack[-1][5] if do_stack else output
                dest.append(out)

            elif tag == 'do':
                out = self.checkStmt(node)
                _, lbl, var_out, start_out, end_out, step_out = out
                do_stack.append([lbl, var_out, start_out, end_out, step_out, []])

            elif tag == 'labeled':
                _, lbl, inner = node
                if inner[0] == 'continue' and do_stack and do_stack[-1][0] == lbl:
                    # matching CONTINUE closes the innermost DO loop
                    frame   = do_stack.pop()
                    do_loop = ('do_loop', frame[1], frame[2], frame[3], frame[4], frame[5])
                    dest    = do_stack[-1][5] if do_stack else output
                    dest.append(do_loop)
                else:
                    out  = self.checkStmt(node)
                    dest = do_stack[-1][5] if do_stack else output
                    dest.append(out)

        if do_stack:
            self.error(f"DO loop with label {do_stack[-1][0]} was never terminated")

        return output

    def analyseUnit(self, unit):
        tag = unit[0]

        if tag == 'program':
            _, name, stmts = unit
            self.symtab = {}
            self.offset = 0
            self.labels = set()
            new_stmts = self.analyseStmts(stmts)
            return ('program', name, new_stmts) , self.symtab

        if tag == 'function':
            _, return_type, name, params, stmts = unit
            self.symtab = {}
            self.offset = 0
            self.labels = set()
            self.symtab[name] = {'type': return_type, 'kind': 'scalar', 'offset': self.offset}
            self.offset += 1
            for pname in params:
                self.symtab[pname] = {'type': None, 'kind': 'param', 'offset': self.offset}
                self.offset += 1
            new_stmts = self.analyseStmts(stmts)
            return ('function', return_type, name, params, new_stmts) , self.symtab

        if tag == 'subroutine':
            _, name, params, stmts = unit
            self.symtab = {}
            self.offset = 0
            self.labels = set()
            for pname in params:
                self.symtab[pname] = {'type': None, 'kind': 'param', 'offset': self.offset}
                self.offset += 1
            new_stmts = self.analyseStmts(stmts)
            return ('subroutine', name, params, new_stmts) , self.symtab
