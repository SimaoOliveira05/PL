from ir import *

class IRGenerator:
    varCounter: int
    labelCounter: int
    currProcedure: Procedure

    def __init__(self):
        self.varCounter = 0
        self.labelCounter = 0

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

    def exprType(self, node):
        tag = node[0]
        if tag == 'var':
            return node[2]
        if tag == 'arr_ref':
            return node[3]
        return node[-1]

    def gen_expr(self, node):
        nodeType = node[0]

        if nodeType in ["int", "real", "bool", "str"]:
            return node[1]

        elif nodeType == "var":
            return node[1]

        elif nodeType == "binop":
            leftResult = self.gen_expr(node[2])
            rightResult = self.gen_expr(node[3])
            temp = self.new_temp()
            self.emit(Binop(temp, node[1], leftResult, rightResult))
            return temp

        elif nodeType == "unary":
            result = self.gen_expr(node[2])
            temp = self.new_temp()
            op = node[1]
            if op == '-':
                op = 'FNEG' if node[3] == 'REAL' else 'NEG'
            self.emit(Unary(temp, op, result))
            return temp

        elif nodeType == "coerce":
            result = self.gen_expr(node[2])
            temp = self.new_temp()
            self.emit(Coerce(temp, node[1], result))
            return temp

        elif nodeType == "arr_ref":
            temp = self.new_temp()
            result = self.gen_expr(node[2])
            self.emit(LoadArr(temp, node[1], result))
            return temp

        elif nodeType == "call":
            temp = self.new_temp()
            args = [self.gen_expr(argNode) for argNode in node[2]]
            self.emit(Call(temp, node[1], args))
            return temp

    def gen_stmt(self, node):
        nodeType = node[0]

        if nodeType == "assign":
            rightResult = self.gen_expr(node[2])
            if node[1][0] == "arr_ref":
                result = self.gen_expr(node[1][2])
                self.emit(StoreArr(node[1][1], result, rightResult))
            else:
                self.emit(Copy(node[1][1], rightResult))

        elif nodeType == "print":
            results = []
            for expr in node[1]:
                val = self.gen_expr(expr)
                type_ = self.exprType(expr)
                results.append((val, type_))
            self.emit(Print(results))

        elif nodeType == "read":
            for expr in node[1]:
                if expr[0] == "arr_ref":
                    result = self.gen_expr(expr[2])
                    self.emit(ReadArr(expr[1], result))
                else:
                    self.emit(Read(expr[1]))

        elif nodeType == "if":
            cond_result = self.gen_expr(node[1])
            if node[3] is not None:
                else_label = self.new_label()
                end_label = self.new_label()
                self.emit(Jz(else_label, cond_result))
                for stmt in node[2]:
                    self.gen_stmt(stmt)
                self.emit(Jump(end_label))
                self.emit(Label(else_label))
                for stmt in node[3]:
                    self.gen_stmt(stmt)
                self.emit(Label(end_label))
            else:
                end_label = self.new_label()
                self.emit(Jz(end_label, cond_result))
                for stmt in node[2]:
                    self.gen_stmt(stmt)
                self.emit(Label(end_label))

        elif nodeType == "labeled":
            self.emit(Label(node[1]))
            self.gen_stmt(node[2])

        elif nodeType == "do_loop":
            var_name = node[1][1]
            var_type = node[1][2]

            sub_op = 'FSUB'   if var_type == 'REAL' else 'SUB'
            mul_op = 'FMUL'   if var_type == 'REAL' else 'MUL'
            cmp_op = 'FSUPEQ' if var_type == 'REAL' else 'SUPEQ'
            add_op = 'FADD'   if var_type == 'REAL' else 'ADD'
            zero   = 0.0      if var_type == 'REAL' else 0

            start_val = self.gen_expr(node[2])
            self.emit(Copy(var_name, start_val))
            step_val = self.gen_expr(node[4])

            start_label = self.new_label()
            end_label = self.new_label()
            self.emit(Label(start_label))

            var_temp = self.gen_expr(node[1])
            end_temp = self.gen_expr(node[3])

            diff_temp = self.new_temp()
            self.emit(Binop(diff_temp, sub_op, end_temp, var_temp))
            prod_temp = self.new_temp()
            self.emit(Binop(prod_temp, mul_op, diff_temp, step_val))
            cond_temp = self.new_temp()
            self.emit(Binop(cond_temp, cmp_op, prod_temp, zero))
            self.emit(Jz(end_label, cond_temp))

            for stmt in node[5]:
                self.gen_stmt(stmt)

            new_var_temp = self.new_temp()
            self.emit(Binop(new_var_temp, add_op, var_temp, step_val))
            self.emit(Copy(var_name, new_var_temp))
            self.emit(Jump(start_label))
            self.emit(Label(end_label))

        elif nodeType == "goto":
            self.emit(Jump(node[1]))

        elif nodeType == "call":
            args = [self.gen_expr(argNode) for argNode in node[2]]
            self.emit(Call(None, node[1], args))

        elif nodeType == "continue":
            pass

        elif nodeType == "return":
            if self.currProcedure.is_function:
                self.emit(Return(self.currProcedure.name))
            else:
                self.emit(Return(None))

    def generate(self, nodeList):
        procedureList = []

        for node, symtab in nodeList:
            opType = node[0]
            if opType == "program":
                procedure = Procedure(symtab, node[1], False, None, "program")
                statements = node[2]
            elif opType == "function":
                procedure = Procedure(symtab, node[2], True, node[1], "function")
                statements = node[4]
            elif opType == "subroutine":
                procedure = Procedure(symtab, node[1], False, None, "subroutine")
                statements = node[3]

            self.currProcedure = procedure

            for stmts in statements:
                self.gen_stmt(stmts)

            if procedure.kind != "program": #emitir Return no fim da procedure no caso de não ter, None se for subroutine (não tem return)
                last = procedure.instructions[-1] if procedure.instructions else None
                if not isinstance(last, Return):
                    if procedure.is_function: #Uma função sem return irá retornar 0 implicitamente (devido ao facto do caller ter alocado 0 para o return)
                        self.emit(Return(procedure.name))
                    else:
                        self.emit(Return(None)) 
            
            procedureList.append(procedure)

        return IRProgram(procedureList)
