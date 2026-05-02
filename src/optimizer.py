from ir import Copy, Binop, Unary, Coerce, LoadArr, StoreArr, Read, ReadArr, Print, Label, Jump, Jz, Call, Return

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

    def isTemp(self, name):
        return isinstance(name, str) and name.startswith('t') and name[1:].isdigit()

    def get_dst(self, instr):
        if isinstance(instr, (Copy, Binop, Unary, Coerce, LoadArr)):
            return instr.dst
        if isinstance(instr, Call) and instr.dst is not None:
            return instr.dst
        return None

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
            # substituição nos campos de cada dataclass
            if isinstance(instr, Copy):
                new_src = subst.get(instr.src, instr.src) if isinstance(instr.src, str) else instr.src
                if new_src != instr.src:
                    changed = True
                instr = Copy(instr.dst, new_src)

            elif isinstance(instr, Binop):
                new_l = subst.get(instr.left,  instr.left)  if isinstance(instr.left,  str) else instr.left
                new_r = subst.get(instr.right, instr.right) if isinstance(instr.right, str) else instr.right
                if new_l != instr.left or new_r != instr.right:
                    changed = True
                instr = Binop(instr.dst, instr.op, new_l, new_r)

            elif isinstance(instr, Unary):
                new_src = subst.get(instr.src, instr.src) if isinstance(instr.src, str) else instr.src
                if new_src != instr.src:
                    changed = True
                instr = Unary(instr.dst, instr.op, new_src)

            elif isinstance(instr, Coerce):
                new_src = subst.get(instr.src, instr.src) if isinstance(instr.src, str) else instr.src
                if new_src != instr.src:
                    changed = True
                instr = Coerce(instr.dst, instr.op, new_src)

            elif isinstance(instr, LoadArr):
                new_idx = subst.get(instr.idx, instr.idx) if isinstance(instr.idx, str) else instr.idx
                if new_idx != instr.idx:
                    changed = True
                instr = LoadArr(instr.dst, instr.name, new_idx)

            elif isinstance(instr, StoreArr):
                new_idx = subst.get(instr.idx, instr.idx) if isinstance(instr.idx, str) else instr.idx
                new_val = subst.get(instr.val, instr.val) if isinstance(instr.val, str) else instr.val
                if new_idx != instr.idx or new_val != instr.val:
                    changed = True
                instr = StoreArr(instr.name, new_idx, new_val)

            elif isinstance(instr, Jz):
                new_cond = subst.get(instr.cond, instr.cond) if isinstance(instr.cond, str) else instr.cond
                if new_cond != instr.cond:
                    changed = True
                instr = Jz(instr.label, new_cond)

            elif isinstance(instr, Print):
                new_vals = []
                for val, t in instr.vals:
                    new_val = subst.get(val, val) if isinstance(val, str) else val
                    if new_val != val:
                        changed = True
                    new_vals.append((new_val, t))
                instr = Print(new_vals)

            elif isinstance(instr, Call):
                new_args = [subst.get(a, a) if isinstance(a, str) else a for a in instr.args]
                if new_args != instr.args:
                    changed = True
                instr = Call(instr.dst, instr.name, new_args)

            # regista cópias simples
            if isinstance(instr, Copy):
                subst[instr.dst] = instr.src

            # invalida substituições cujo dst foi reatribuído
            dst = self.get_dst(instr)
            if dst is not None:
                subst = {k: v for k, v in subst.items() if k != dst and v != dst}

            new_instructions.append(instr)

        proc.instructions = new_instructions
        return changed

    def dead_code_elimination(self, proc):
        # recolhe todos os temps lidos
        used = set()
        for instr in proc.instructions:
            dst = self.get_dst(instr)
            for val in vars(instr).values():
                if self.isTemp(val) and val != dst:
                    used.add(val)
                elif isinstance(val, list):
                    for item in val:
                        if self.isTemp(item):
                            used.add(item)
                        elif isinstance(item, tuple):
                            for subitem in item:
                                if self.isTemp(subitem):
                                    used.add(subitem)

        # elimina instruções cujo dst é um temp nunca lido
        new_instructions = []
        changed = False
        for instr in proc.instructions:
            dst = self.get_dst(instr)
            if dst is not None and self.isTemp(dst) and dst not in used:
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
