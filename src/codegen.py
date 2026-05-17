from ir import (
    is_temp,
    Copy, Binop, Unary, Coerce,
    LoadArr, StoreArr, Read, ReadArr,
    Print, Label, Jump, Jz,
    Call, Return,
    INTRINSIC_OPCODES,
    KIND_ARRAY, KIND_DYN_ARRAY, KIND_PARAM, KIND_ARRAY_PARAM,
    KIND_PROGRAM,
)

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

    def buildFrame(self, procedure):
        self.frameMap = {}
        self.useLocal = procedure.kind != KIND_PROGRAM
        self.nParams = 0

        if not self.useLocal:
            pos = 0
            for name, info in self.symtab.items():
                info['offset'] = pos
                pos += 1
            self.localSize = pos
            return

        params = [n for n, info in self.symtab.items() if info.get('kind') in (KIND_PARAM, KIND_ARRAY_PARAM)]
        n_params = len(params)
        self.nParams = n_params # nParams é guardado para o codegen do RETURN saber onde está o slot de retorno: -(nParams+1)
        for i, name in enumerate(params): # Atribui offsets negativos aos params. Com 2 params (A, N): A → -2, N → -1. Ficam abaixo do FP porque foram empilhados pelo caller antes do CALL.
            self.symtab[name]['offset'] = i - n_params 

        pos = 0
        for name, info in self.symtab.items(): #
            if info.get('kind') in (KIND_PARAM, KIND_ARRAY_PARAM):
                continue
            info['offset'] = pos # temos que dar overrite ao offset na variavel por causa que estamos dentro de uma função
            pos += 1
        self.localSize = pos

    def collectTemps(self, procedure):
        tempSet = set()
        for instr in procedure.instructions:
            tempSet |= instr.uses()
            dst = instr.get_dst()
            if dst is not None and is_temp(dst):
                tempSet.add(dst)
        ordered = sorted(tempSet, key=lambda t: int(t[1:]))
        base = self.localSize
        self.temps = {name: base + offset for offset, name in enumerate(ordered)}

    def varOffset(self, name):
        return self.symtab[name]['offset']

    def arrayBase(self, name):
        op = "PUSHL " if self.useLocal else "PUSHG "
        self.emit(op + str(self.varOffset(name)))


    def push(self, name):
        if isinstance(name, bool):
            self.emit(f"PUSHI {1 if name else 0}")
        elif isinstance(name, int):
            self.emit(f"PUSHI {name}")
        elif isinstance(name, float):
            self.emit(f"PUSHF {name}")
        elif isinstance(name, str):
            if is_temp(name):
                self.emit(f"PUSHL {self.temps[name]}")
            elif name in self.symtab:
                op = "PUSHL" if self.useLocal else "PUSHG"
                self.emit(f"{op} {self.varOffset(name)}")
            else:
                self.emit(f'PUSHS "{name}"')

    def store(self, name):
        if is_temp(name):
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

        if procedure.kind == KIND_PROGRAM:
            self.emit("START")
        else:
            self.emit(procedure.name + ":")

        self.emit("PUSHN " + str(self.localSize + len(self.temps)))

        for name, info in self.symtab.items():
            if info['kind'] == KIND_ARRAY:
                self.emit("ALLOC " + str(info['size']))
                self.store(name)
            elif info['kind'] == KIND_DYN_ARRAY:
                self.push(info['size'])   # size é o nome do parâmetro ex: 'N'
                self.emit("ALLOCN")
                self.store(name)

        for instr in procedure.instructions:

            if isinstance(instr, Copy):
                self.push(instr.src)
                self.store(instr.dst)

            elif isinstance(instr, Binop):
                self.push(instr.left)
                self.push(instr.right)
                if instr.op == 'NEQ':
                    # VM has no NEQ — negate EQUAL
                    self.emit('EQUAL')
                    self.emit('NOT')
                else:
                    self.emit(instr.op)
                self.store(instr.dst)

            elif isinstance(instr, Coerce):
                self.push(instr.src)
                self.emit(instr.op)
                self.store(instr.dst)

            elif isinstance(instr, Unary):
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
                self.emit("PUSHI 1") #TEmos que decrementar em 1 pois FORTRAN use 1 indexed arrays :P
                self.emit("SUB")
                self.emit("PADD")
                self.emit("LOAD 0")
                self.store(instr.dst)

            elif isinstance(instr, StoreArr):
                self.arrayBase(instr.name)
                self.push(instr.idx)
                self.emit("PUSHI 1") #TEmos que decrementar em 1 pois FORTRAN use 1 indexed arrays :P
                self.emit("SUB")
                self.emit("PADD")
                self.push(instr.val)
                self.emit("STORE 0")

            elif isinstance(instr, ReadArr):
                self.arrayBase(instr.name)
                self.push(instr.idx)
                self.emit("PUSHI 1") #TEmos que decrementar em 1 pois FORTRAN use 1 indexed arrays :P
                self.emit("SUB")
                self.emit("PADD")
                self.emit("READ")
                if self.symtab[instr.name]['type'] == "INTEGER":
                    self.emit("ATOI")
                else:
                    self.emit("ATOF")
                self.emit("STORE 0")

            elif isinstance(instr, Call):
                n_args = len(instr.args)
                is_user_func = instr.dst is not None and instr.name not in INTRINSIC_OPCODES
                if is_user_func:
                    self.emit("PUSHI 0")
                for arg in instr.args:
                    self.push(arg)
                if instr.name in INTRINSIC_OPCODES:
                    self.emit(INTRINSIC_OPCODES[instr.name])
                else:
                    self.emit(f"PUSHA {instr.name}")
                    self.emit("CALL")
                    if n_args > 0:
                        self.emit(f"POP {n_args}")
                if instr.dst is not None:
                    self.store(instr.dst)

            elif isinstance(instr, Return):
                if instr.val is not None:
                    self.push(instr.val)
                    self.emit(f"STOREL {-(self.nParams + 1)}")
                self.emit("POP " + str(self.localSize + len(self.temps)))
                self.emit("RETURN")

        if procedure.kind == KIND_PROGRAM:
            self.emit("STOP")

