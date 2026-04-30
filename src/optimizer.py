OP_EVAL = {
    'ADD':    lambda a, b: a + b,
    'SUB':    lambda a, b: a - b,
    'MUL':    lambda a, b: a * b,
    'DIV':    lambda a, b: a // b, #fortran truncates int / int
    'FADD':   lambda a, b: a + b,
    'FSUB':   lambda a, b: a - b,
    'FMUL':   lambda a, b: a * b,
    'FDIV':   lambda a, b: a / b,
    'EQUAL':  lambda a, b: int(a == b),
    'NEQ':    lambda a, b: int(a != b),
    'INF':    lambda a, b: int(a <  b),
    'INFEQ':  lambda a, b: int(a <= b),
    'SUP':    lambda a, b: int(a >  b),
    'SUPEQ':  lambda a, b: int(a >= b),
    'FINF':   lambda a, b: int(a <  b),
    'FINFEQ': lambda a, b: int(a <= b),
    'FSUP':   lambda a, b: int(a >  b),
    'FSUPEQ': lambda a, b: int(a >= b),
    'AND':    lambda a, b: int(bool(a) and bool(b)),
    'OR':     lambda a, b: int(bool(a) or  bool(b)),
}



class Optimizer:

    def constant_folding(proc):
        new_instructions = []
        changed = False
        for instruction in proc.instructions:
            if instruction[0] == "binop":
                a,b = instruction[3], instruction[4]
                if not isinstance(a,str) and not isinstance(b,str):
                    value = OP_EVAL[instruction[2]](a,b)
                    new_instructions.append(("copy",instruction[1],value))
                    changed = True
                    continue
            new_instructions.append(instruction)

        proc.instructions = new_instructions
        return changed



    def optimize(self, procedures):
        for proc in procedures:
            changed = True
            while changed:
              pass  
    
