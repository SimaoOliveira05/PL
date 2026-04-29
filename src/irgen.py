# ── Nós de expressão produzidos pelo semantic analyser ────────────────────────
#
#   ('var',        name, type, offset) DONE
#   ('int',        value, 'INTEGER') DONE
#   ('real',       value, 'REAL') DONE
#   ('bool',       value, 'LOGICAL') DONE
#   ('str',        value, 'CHARACTER') DONE
#   ('binop',      op, left, right, type)      op: 'ADD','SUB','MUL','DIV','FADD',... DONE
#   ('unary',      op, operand, type)          op: 'NEG', 'NOT' DONE
#   ('coerce',     'ITOF', expr, 'REAL') DONE
#   ('arr_ref',    name, idx_expr, type, offset) DONE
#   ('call',       name, [args], type)          chamada de função em posição de expressão DONE
#
# ── Nós de statement ──────────────────────────────────────────────────────────
#
#   ('decl',    type_str, [var_decls]) DONE (não é preciso fazer absolutamente nada)
#   ('assign',  lhs, rhs)                       DONE
#   ('if',      cond, then_stmts, else_stmts_or_None) DONE
#   ('do_loop', var, start, end, step_or_None, body_stmts) DONE
#   ('labeled', label_int, stmt) DONE
#   ('goto',    label_int) DONE
#   ('read',    [lvalues]) DONE
#   ('print',   [exprs]) DONE
#   ('call',    name, [args]) DONE
#   ('return',)
#   ('continue',) DONE (não é preciso fazer absolutamente nada)
#
# ── Nós de unidade (topo da AST) ──────────────────────────────────────────────
#
#   ('program',    name_or_None, stmt_list) DONE
#   ('function',   return_type, name, params, stmt_list) DONE
#   ('subroutine', name, params, stmt_list) DONE

class Procedure:
    name: str
    symtab: dict
    instructions: list
    is_function: bool
    return_type: str | None
    kind: str

    def __init__(self,symtab,name,is_function,return_type,kind):
        self.name = name
        self.symtab = symtab
        self.is_function = is_function
        self.return_type = return_type
        self.instructions = []
        self.kind = kind



class IRProgram:
    procedures : list[Procedure]


class IRGenerator:
    varCounter: int
    labelCounter: int
    currProcedure: Procedure

    def __init__(self):
        self.varCounter = 0
        self.labelCounter = 0

    def new_temp(self):
        var = "t"+str(self.varCounter)
        self.varCounter += 1
        return var
    
    def new_label(self):
        label = "l"+str(self.labelCounter)
        self.labelCounter +=1
        return label

    
    def emit(self,instruction):
        self.currProcedure.instructions.append(instruction)

    def exprType(self, node):
        tag = node[0]
        if tag == 'var':                   
            return node[2]
        if tag == 'arr_ref':               
            return node[3]
        return node[-1]
                           

    def gen_expr(self,node):

        nodeType = node[0]

        if nodeType in ["int", "real","bool","str"]:
            return node[1]
        
        elif nodeType == "var":
            return node[1]
        
        elif nodeType == "binop":
            leftResult = self.gen_expr(node[2])
            rightResult = self.gen_expr(node[3])
            temp = self.new_temp()
            self.emit(("binop", temp, node[1], leftResult, rightResult))
            return temp

        elif nodeType == "unary":
            result = self.gen_expr(node[2])
            temp = self.new_temp()
            self.emit(("unary", temp, node[1],result))
            return temp
        
        elif nodeType == "coerce":
            result = self.gen_expr(node[2])
            temp = self.new_temp()
            self.emit(("coerce", temp, node[1], result))
            return temp

        elif nodeType == "arr_ref":
            #   ('arr_ref',    name, idx_expr, type, offset)
            temp = self.new_temp()
            result = self.gen_expr(node[2])
            self.emit(('load_arr', temp, node[1], result))
            return temp
        

        elif nodeType == "call":
            #('call', name, [args], type)
            temp = self.new_temp()
            args = []
            for argNode in node[2]:
                args.append(self.gen_expr(argNode))
            self.emit(("call", temp, node[1], args))
            return temp


    def gen_stmt(self,node):
        
        nodeType = node[0]

        if nodeType == "assign":
            rightResult = self.gen_expr(node[2])
            if node[1][0] == "arr_ref":
                result = self.gen_expr(node[1][2])
                self.emit(("store_arr", node[1][1], result, rightResult))
            else:
                self.emit(("copy",node[1][1],rightResult))

        if nodeType == "print":
            results = []
            for expr in node[1]:
                val  = self.gen_expr(expr)
                type_ = self.exprType(expr)
                results.append((val, type_))
            self.emit(("print", results))

        if nodeType == "read":
            results = []
            for expr in node[1]:
                if expr[0] == "arr_ref":
                    result = self.gen_expr(expr[2])
                    self.emit(("read_arr", expr[1], result))
                else:
                    self.emit(("read", expr[1]))

        if nodeType == "if":
            #   ('if',      cond, then_stmts, else_stmts_or_None)
            cond_result = self.gen_expr(node[1])
            if node[3] is not None:
                else_label = self.new_label()
                end_label  = self.new_label()
                self.emit(("jz", else_label, cond_result))
                for stmt in node[2]:
                    self.gen_stmt(stmt)
                self.emit(("jump", end_label))
                self.emit(("label", else_label))
                for stmt in node[3]:
                    self.gen_stmt(stmt)
                self.emit(("label", end_label))
            else:
                end_label = self.new_label()
                self.emit(("jz", end_label, cond_result))
                for stmt in node[2]:
                    self.gen_stmt(stmt)
                self.emit(("label", end_label))
        
        if nodeType == "labeled":
            #   ('labeled', label_int, stmt)
            self.emit(("label",node[1]))
            result = self.gen_stmt(node[2])

        if nodeType == "do_loop":
            #   ('do_loop', var, start, end, step_or_None, body_stmts)
            var_name  = node[1][1]
            start_val = self.gen_expr(node[2])
            self.emit(("copy", var_name, start_val))
            start_label = self.new_label()
            end_label   = self.new_label()
            self.emit(("label", start_label))
            var_temp  = self.gen_expr(node[1])
            end_temp  = self.gen_expr(node[3])
            cond_temp = self.new_temp()
            self.emit(('binop', cond_temp, 'INFEQ', var_temp, end_temp))
            self.emit(("jz", end_label, cond_temp))
            for stmt in node[5]:
                self.gen_stmt(stmt)
            step_temp    = self.gen_expr(node[4])
            new_var_temp = self.new_temp()
            self.emit(('binop', new_var_temp, 'ADD', var_temp, step_temp))
            self.emit(('copy', var_name, new_var_temp))
            self.emit(("jump", start_label))
            self.emit(("label", end_label))
        
        if nodeType == "goto":
            self.emit(("jump",node[1]))
        
        if nodeType == "call":
            #   ('call',    name, [args])
            args = []
            for argNode in node[2]:
                args.append(self.gen_expr(argNode))
            self.emit(("call", None, node[1], args))
        
        if nodeType == "return":
            if self.currProcedure.is_function:
                self.emit(('return', self.currProcedure.name))
            else:
                self.emit(('return', None))





    
    def generate(self,nodeList):
        #   ('program',    name_or_None, stmt_list)
        #   ('function',   return_type, name, params, stmt_list)
        #   ('subroutine', name, params, stmt_list)
        procedureList = []

        for node, symtab in nodeList:
            type = node[0]
            if type == "program":
                procedure = Procedure(symtab,node[1],False,None,"program")
                statements = node[2]
            elif type == "function":
                procedure = Procedure(symtab,node[2],True,node[1],"function")
                statements = node[4]

            elif type == "subroutine":
                procedure = Procedure(symtab,node[1],False,None,"subroutine")
                statements = node[3]


            self.currProcedure = procedure

            for stmts in statements:
                self.gen_stmt(stmts)

            procedureList.append(procedure)

        return procedureList

            
