from ir import *

OP_EVAL = {
    'ADD':    lambda a, b: a + b,
    'SUB':    lambda a, b: a - b,
    'MUL':    lambda a, b: a * b,
    'DIV':    lambda a, b: a // b,  # fortran truncates int / int
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

    def constant_folding(self, proc):
        new_instructions = []
        changed = False
        for instr in proc.instructions:
            if isinstance(instr, Binop):
                a, b = instr.left, instr.right
                if not isinstance(a, str) and not isinstance(b, str):
                    value = OP_EVAL[instr.op](a, b)
                    new_instructions.append(Copy(instr.dst, value))
                    changed = True
                    continue
            new_instructions.append(instr)
        proc.instructions = new_instructions
        return changed

    def copy_propagation(self, proc):
        subst = {}
        new_instructions = []
        changed = False

        for instr in proc.instructions:
            new_instr = instr.substitute(subst)
            if new_instr != instr:
                changed = True
            instr = new_instr

            # regista cópias simples temp→valor para substituições futuras
            if isinstance(instr, Copy):
                subst[instr.dst] = instr.src

            # invalida substituições cujo dst foi reatribuído
            dst = instr.get_dst()
            if dst is not None:
                subst = {k: v for k, v in subst.items() if k != dst and v != dst}

            new_instructions.append(instr)

        proc.instructions = new_instructions
        return changed

    def dead_code_elimination(self, proc):
        # recolhe todos os temps lidos em qualquer instrução
        used = set()
        for instr in proc.instructions:
            used |= instr.uses()

        # elimina instruções cujo dst é um temp nunca lido
        new_instructions = []
        changed = False
        for instr in proc.instructions:
            dst = instr.get_dst()
            if dst is not None and is_temp(dst) and dst not in used:
                changed = True
                continue
            new_instructions.append(instr)

        proc.instructions = new_instructions
        return changed

    def optimize(self, procedures):
        for proc in procedures:
            changed = True
            while changed:
                changed  = self.constant_folding(proc)
                changed |= self.copy_propagation(proc)
                changed |= self.dead_code_elimination(proc)
        return procedures
