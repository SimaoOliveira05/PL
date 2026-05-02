from irgen import Procedure
from ir import *
from ir import INTRINSICS as _INTRINSICS


class CodeGenerator:

    output: list
    temps: dict
    symtab: dict
    frameMap: dict
    useLocal: bool
    localSize: int

    def __init__(self):
        self.output = []
        self.symtab = {}
        self.temps = {}
        self.frameMap = {}
        self.useLocal = False
        self.localSize = 0

    def emit(self, line):
        self.output.append(line)

    def isTemp(self, name):
        return isinstance(name, str) and name.startswith('t') and name[1:].isdigit()

    def globalsSize(self):
        size = 0
        for info in self.symtab.values():
            end = info['offset'] + (info['size'] if info['kind'] == 'array' else 1)
            if end > size:
                size = end
        return size

    def buildFrame(self, procedure):
        self.frameMap = {}
        self.useLocal = procedure.kind != "program"

        if not self.useLocal:
            self.localSize = self.globalsSize()
            return

        params = [n for n, info in self.symtab.items() if info.get('kind') == 'param']
        n_params = len(params)
        for i, name in enumerate(params):
            self.frameMap[name] = i - n_params

        pos = 0
        for name, info in self.symtab.items():
            if info.get('kind') == 'param':
                continue
            self.frameMap[name] = pos
            pos += info['size'] if info['kind'] == 'array' else 1
        self.localSize = pos

    def collectTemps(self, procedure):
        tempSet = set()
        for instr in procedure.instructions:
            for val in vars(instr).values():
                if self.isTemp(val):
                    tempSet.add(val)
                elif isinstance(val, list):
                    for item in val:
                        if self.isTemp(item):
                            tempSet.add(item)
                        elif isinstance(item, tuple):
                            for subitem in item:
                                if self.isTemp(subitem):
                                    tempSet.add(subitem)
        ordered = sorted(tempSet, key=lambda t: int(t[1:]))
        base = self.localSize
        self.temps = {name: base + offset for offset, name in enumerate(ordered)}

    def varOffset(self, name):
        if self.useLocal:
            return self.frameMap[name]
        return self.symtab[name]['offset']

    def arrayBase(self, name):
        self.emit("PUSHFP" if self.useLocal else "PUSHGP")
        self.push(self.varOffset(name))
        self.emit("PADD")

    def push(self, name):
        if isinstance(name, bool):
            name = 1 if name else 0

        if isinstance(name, int):
            self.emit(f"PUSHI {name}")

        elif isinstance(name, float):
            self.emit(f"PUSHF {name}")

        elif isinstance(name, str):
            if self.isTemp(name):
                self.emit(f"PUSHL {self.temps[name]}")
            elif name in self.symtab:
                op = "PUSHL" if self.useLocal else "PUSHG"
                self.emit(f"{op} {self.varOffset(name)}")
            else:
                self.emit(f'PUSHS "{name}"')

    def store(self, name):
        if self.isTemp(name):
            self.emit(f"STOREL {self.temps[name]}")
        elif name in self.symtab:
            op = "STOREL" if self.useLocal else "STOREG"
            self.emit(f"{op} {self.varOffset(name)}")
        else:
            self.emit(f'STORES "{name}"')

    def genProcedure(self, procedure):
        self.symtab = procedure.symtab
        self.buildFrame(procedure)
        self.collectTemps(procedure)

        if procedure.kind == "program":
            self.emit("START")
        else:
            self.emit(procedure.name + ":")

        self.emit("PUSHN " + str(self.localSize + len(self.temps)))

        for instr in procedure.instructions:

            if isinstance(instr, Copy):
                self.push(instr.src)
                self.store(instr.dst)

            elif isinstance(instr, Binop):
                self.push(instr.left)
                self.push(instr.right)
                self.emit(instr.op)
                self.store(instr.dst)

            elif isinstance(instr, Coerce):
                self.push(instr.src)
                self.emit(instr.op)
                self.store(instr.dst)

            elif isinstance(instr, Unary):
                if instr.op == 'NEG':
                    self.emit("PUSHI 0")
                    self.push(instr.src)
                    self.emit("SUB")
                elif instr.op == 'FNEG':
                    self.emit("PUSHF 0.0")
                    self.push(instr.src)
                    self.emit("FSUB")
                else:
                    self.push(instr.src)
                    self.emit(instr.op)
                self.store(instr.dst)

            elif isinstance(instr, Label):
                self.emit(str(instr.name) + ":")

            elif isinstance(instr, Jump):
                self.emit("JUMP " + str(instr.label))

            elif isinstance(instr, Read):
                self.emit("READ")
                if self.symtab[instr.var]['type'] == "INTEGER":
                    self.emit("ATOI")
                else:
                    self.emit("ATOF")
                self.store(instr.var)

            elif isinstance(instr, Print):
                for val, typ in instr.vals:
                    self.push(val)
                    if typ in ('INTEGER', 'LOGICAL'):
                        self.emit("WRITEI")
                    elif typ == 'REAL':
                        self.emit("WRITEF")
                    else:
                        self.emit("WRITES")
                self.emit("WRITELN")

            elif isinstance(instr, Jz):
                self.push(instr.cond)
                self.emit("JZ " + instr.label)

            elif isinstance(instr, LoadArr):
                self.arrayBase(instr.name)
                self.push(instr.idx)
                self.emit("PADD")
                self.emit("LOAD 0")
                self.store(instr.dst)

            elif isinstance(instr, StoreArr):
                self.arrayBase(instr.name)
                self.push(instr.idx)
                self.emit("PADD")
                self.push(instr.val)
                self.emit("STORE 0")

            elif isinstance(instr, ReadArr):
                self.arrayBase(instr.name)
                self.push(instr.idx)
                self.emit("PADD")
                self.emit("READ")
                if self.symtab[instr.name]['type'] == "INTEGER":
                    self.emit("ATOI")
                else:
                    self.emit("ATOF")
                self.emit("STORE 0")

            elif isinstance(instr, Call):
                for arg in instr.args:
                    self.push(arg)
                if instr.name in _INTRINSICS:
                    self.emit(_INTRINSICS[instr.name])
                else:
                    self.emit(f"PUSHA {instr.name}")
                    self.emit("CALL")
                if instr.dst is not None:
                    self.store(instr.dst)

            elif isinstance(instr, Return):
                if instr.val is not None:
                    self.push(instr.val)
                self.emit("RETURN")

        if procedure.kind == "program":
            self.emit("STOP")
