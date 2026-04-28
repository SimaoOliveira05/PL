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
#   ('call_or_arr',name, [args], type)         chamada de função em posição de expressão DONE
#
# ── Nós de statement ──────────────────────────────────────────────────────────
#
#   ('decl',    type_str, [var_decls])
#   ('assign',  lhs, rhs)                       DONE
#   ('if',      cond, then_stmts, else_stmts_or_None)
#   ('do_loop', var, start, end, step_or_None, body_stmts)
#   ('labeled', label_int, stmt)
#   ('goto',    label_int)
#   ('read',    [lvalues]) DONE
#   ('print',   [exprs]) DONE
#   ('call',    name, [args])
#   ('return',)
#   ('continue',)
#
# ── Nós de unidade (topo da AST) ──────────────────────────────────────────────
#
#   ('program',    name_or_None, stmt_list)
#   ('function',   return_type, name, params, stmt_list)
#   ('subroutine', name, params, stmt_list)

class Procedure:
    name: str
    symtab: dict
    instructions: list
    is_function: bool
    return_type: str | None

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

    def gen_expr(self,node):

        nodeType = node[0]

        if nodeType in ["int", "real","bool","str"]:
            temp = self.new_temp()
            self.emit(("copy", temp, node[1]))
            return temp
        
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
            self.emit(('load_arr', temp, node[1], result, node[4]))
            return temp
        

        elif nodeType == "call_or_arr":
            #('call_or_arr',name, [args], type) 
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
                self.emit(("store_arr",node[1][1],result,node[1][4],rightResult))
            else:
                self.emit(("copy",node[1][1],rightResult))

        if nodeType == "print":
            results = []
            for expr in node[1]:
                results.append(self.gen_expr(expr))
            self.emit(("print",results))

        if nodeType == "read":
            results = []
            for expr in node[1]:
                if expr[0] == "arr_ref":
                    result = self.gen_expr(expr[2])
                    self.emit(("read_arr",expr[1],result,expr[4]))
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

            
