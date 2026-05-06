import dataclasses
from ir import is_temp, Copy, Binop

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

    def temp_forwarding(self, proc):
        """SomeOp(dst=t) + Copy(dst=X, src=t) where t used once → SomeOp(dst=X)."""
        use_count = {}
        for instr in proc.instructions:
            for t in instr.uses():
                use_count[t] = use_count.get(t, 0) + 1

        # temps used exactly once, in a Copy
        instrs = proc.instructions
        forward = {}
        for i, instr in enumerate(instrs):
            if not (isinstance(instr, Copy) and is_temp(instr.src) and use_count.get(instr.src, 0) == 1):
                continue
            # find the producer of instr.src — must be the immediately previous instruction
            if i == 0:
                continue
            prev = instrs[i-1]
            if prev.get_dst() != instr.src:
                continue
            # also: the Copy's destination must not be read by `prev` itself
            if instr.dst in prev.uses():
                continue

            forward[instr.src] = instr.dst  

        if not forward:
            return False

        new_instructions = []
        for instr in proc.instructions:
            if isinstance(instr, Copy) and instr.src in forward:
                continue
            dst = instr.get_dst()
            if dst is not None and dst in forward:
                instr = dataclasses.replace(instr, dst=forward[dst])
            new_instructions.append(instr)

        proc.instructions = new_instructions
        return True

    def optimize(self, procedures):
        for proc in procedures:
            changed = True
            while changed:
                changed  = self.constant_folding(proc)
                changed |= self.temp_forwarding(proc)
                changed |= self.copy_propagation(proc)
                changed |= self.dead_code_elimination(proc)
        return procedures
