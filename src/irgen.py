import ir
from ir import KIND_PROGRAM, KIND_FUNCTION, KIND_SUBROUTINE
from ast_nodes import (
    Program, Function, Subroutine,
    Assign, If, Goto, Continue, Return, Read, Print,
    CallStmt, Labeled, DoLoop,
    IntLit, RealLit, StrLit, BoolLit,
    Var, ArrRef, Binop, Unary, CallExpr, Coerce,
)


class IRGenerator:

    def __init__(self):
        self.varCounter = 0
        self.labelCounter = 0
        self.currProcedure = None

    def new_temp(self):
        var = "t" + str(self.varCounter)
        self.varCounter += 1
        return var

    def new_label(self):
        label = "l" + str(self.labelCounter)
        self.labelCounter += 1
        return label

    def emit(self, instruction):
        self.currProcedure.instructions.append(instruction)

    # ── Expressions ────────────────────────────────────────────────────────────

    def gen_expr(self, node):
        if isinstance(node, (IntLit, RealLit, StrLit, BoolLit)):
            return node.value

        if isinstance(node, Var):
            return node.name

        if isinstance(node, Binop):
            left  = self.gen_expr(node.left)
            right = self.gen_expr(node.right)
            temp  = self.new_temp()
            self.emit(ir.Binop(temp, node.op, left, right))
            return temp

        if isinstance(node, Unary):
            inner = self.gen_expr(node.operand)
            temp  = self.new_temp()
            if node.op == '-':
                # The VM has no NEG/FNEG opcode — express as 0 - x
                zero   = 0.0    if node.type == 'REAL' else 0
                sub_op = 'FSUB' if node.type == 'REAL' else 'SUB'
                self.emit(ir.Binop(temp, sub_op, zero, inner))
            else:
                self.emit(ir.Unary(temp, 'NOT', inner))
            return temp

        if isinstance(node, Coerce):
            inner = self.gen_expr(node.src)
            temp  = self.new_temp()
            self.emit(ir.Coerce(temp, node.op, inner))
            return temp

        if isinstance(node, ArrRef):
            idx  = self.gen_expr(node.idx)
            temp = self.new_temp()
            self.emit(ir.LoadArr(temp, node.name, idx))
            return temp

        if isinstance(node, CallExpr):
            args = [self.gen_expr(a) for a in node.args]
            temp = self.new_temp()
            self.emit(ir.Call(temp, node.name, args))
            return temp

        raise Exception(f'irgen: unknown expression type: {type(node).__name__}')

    # ── Statements ─────────────────────────────────────────────────────────────

    def gen_stmt(self, node):
        if isinstance(node, Assign):
            rhs = self.gen_expr(node.rhs)
            if isinstance(node.lhs, ArrRef):
                idx = self.gen_expr(node.lhs.idx)
                self.emit(ir.StoreArr(node.lhs.name, idx, rhs))
            else:
                self.emit(ir.Copy(node.lhs.name, rhs))
            return

        if isinstance(node, Print):
            results = []
            for e in node.values:
                val = self.gen_expr(e)
                results.append((val, e.type))
            self.emit(ir.Print(results))
            return

        if isinstance(node, Read):
            for e in node.targets:
                if isinstance(e, ArrRef):
                    idx = self.gen_expr(e.idx)
                    self.emit(ir.ReadArr(e.name, idx))
                else:
                    self.emit(ir.Read(e.name))
            return

        if isinstance(node, If):
            cond = self.gen_expr(node.cond)
            if node.else_body is not None:
                else_label = self.new_label()
                end_label  = self.new_label()
                self.emit(ir.Jz(else_label, cond))
                for s in node.then_body:
                    self.gen_stmt(s)
                self.emit(ir.Jump(end_label))
                self.emit(ir.Label(else_label))
                for s in node.else_body:
                    self.gen_stmt(s)
                self.emit(ir.Label(end_label))
            else:
                end_label = self.new_label()
                self.emit(ir.Jz(end_label, cond))
                for s in node.then_body:
                    self.gen_stmt(s)
                self.emit(ir.Label(end_label))
            return

        if isinstance(node, Labeled):
            self.emit(ir.Label(node.label))
            self.gen_stmt(node.stmt)
            return

        if isinstance(node, DoLoop):
            var_name = node.var.name
            var_type = node.var.type

            sub_op = 'FSUB'   if var_type == 'REAL' else 'SUB'
            mul_op = 'FMUL'   if var_type == 'REAL' else 'MUL'
            cmp_op = 'FSUPEQ' if var_type == 'REAL' else 'SUPEQ'
            add_op = 'FADD'   if var_type == 'REAL' else 'ADD'
            zero   = 0.0      if var_type == 'REAL' else 0

            start_val = self.gen_expr(node.start)
            self.emit(ir.Copy(var_name, start_val))
            end_val  = self.gen_expr(node.end)    # evaluated once before the loop
            step_val = self.gen_expr(node.step)

            start_label = self.new_label()
            end_label   = self.new_label()
            self.emit(ir.Label(start_label))

            var_temp = self.gen_expr(node.var)

            diff_temp = self.new_temp()
            self.emit(ir.Binop(diff_temp, sub_op, end_val, var_temp))
            prod_temp = self.new_temp()
            self.emit(ir.Binop(prod_temp, mul_op, diff_temp, step_val))
            cond_temp = self.new_temp()
            self.emit(ir.Binop(cond_temp, cmp_op, prod_temp, zero))
            self.emit(ir.Jz(end_label, cond_temp))

            for s in node.body:
                self.gen_stmt(s)

            new_var_temp = self.new_temp()
            self.emit(ir.Binop(new_var_temp, add_op, var_temp, step_val))
            self.emit(ir.Copy(var_name, new_var_temp))
            self.emit(ir.Jump(start_label))
            self.emit(ir.Label(end_label))
            return

        if isinstance(node, Goto):
            self.emit(ir.Jump(node.label))
            return

        if isinstance(node, CallStmt):
            args = [self.gen_expr(a) for a in node.args]
            self.emit(ir.Call(None, node.name, args))
            return

        if isinstance(node, Continue):
            return

        if isinstance(node, Return):
            if self.currProcedure.is_function:
                self.emit(ir.Return(self.currProcedure.name))
            else:
                self.emit(ir.Return(None))
            return

        raise Exception(f'irgen: unknown statement type: {type(node).__name__}')

    # ── Top level ──────────────────────────────────────────────────────────────

    def generate(self, nodeList):
        procedureList = []

        for unit, symtab in nodeList:
            if isinstance(unit, Program):
                procedure  = ir.Procedure(symtab, unit.name, False, None, KIND_PROGRAM)
                statements = unit.body
            elif isinstance(unit, Function):
                procedure  = ir.Procedure(symtab, unit.name, True, unit.return_type, KIND_FUNCTION)
                statements = unit.body
            elif isinstance(unit, Subroutine):
                procedure  = ir.Procedure(symtab, unit.name, False, None, KIND_SUBROUTINE)
                statements = unit.body
            else:
                raise Exception(f'irgen: unknown program unit: {type(unit).__name__}')

            self.currProcedure = procedure

            for s in statements:
                self.gen_stmt(s)

            # ensure every function/subroutine ends with a Return
            if procedure.kind != KIND_PROGRAM:
                last = procedure.instructions[-1] if procedure.instructions else None
                if not isinstance(last, ir.Return):
                    if procedure.is_function:
                        # implicit return of the function name slot (initialised to 0 by caller)
                        self.emit(ir.Return(procedure.name))
                    else:
                        self.emit(ir.Return(None))

            procedureList.append(procedure)

        return ir.IRProgram(procedureList)
