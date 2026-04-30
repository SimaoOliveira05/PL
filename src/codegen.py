from irgen import Procedure
from intrinsics import INTRINSICS as _INTRINSICS

# ── Instruções TAC produzidas pelo irgen ──────────────────────────────────────
#
#   ('copy',      dst, src)                   atribuição escalar            DONE
#   ('binop',     dst, op, left, right)        operação binária             DONE
#   ('unary',     dst, op, src)               operação unária               DONE
#   ('coerce',    dst, 'ITOF', src)           conversão de tipo             DONE
#   ('load_arr',  dst, name, idx)             leitura de array              DONE
#   ('store_arr', name, idx, val)             escrita em array              DONE
#   ('read',      var)                        leitura escalar de stdin      DONE
#   ('read_arr',  name, idx)                  leitura de array de stdin     DONE
#   ('print',     [vals])                     impressão                     DONE
#   ('label',     name)                       marca posição                 DONE
#   ('jump',      label)                      salto incondicional           DONE
#   ('jz',        label, cond)                salto se zero                 DONE
#   ('call',      dst, name, [args])          chamada de função (dst = temp)
#   ('call',      None, name, [args])         chamada de subrotina
#   ('return',    val_or_None)                retorno


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
        for instruction in procedure.instructions:
            for field in instruction:
                if self.isTemp(field):
                    tempSet.add(field)
        ordered = sorted(tempSet, key=lambda t: int(t[1:]))
        base = self.localSize
        self.temps = {name: base + offset for offset, name in enumerate(ordered)}

    def varOffset(self, name):
        if self.useLocal:
            return self.frameMap[name]
        return self.symtab[name]['offset']

    def arrayBase(self, name):
        # Empilha o endereco base do array (frame ptr + offset).
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
            type = instr[0]

            if type == "copy":
                self.push(instr[2])
                self.store(instr[1])

            if type == "binop":
            #('binop',     dst, op, left, right)        
                self.push(instr[3])
                self.push(instr[4])
                self.emit(instr[2])
                self.store(instr[1])

            if type == "coerce":
                self.push(instr[3])
                self.emit(instr[2])
                self.store(instr[1])

            if type == "unary":
                op  = instr[2]
                src = instr[3]
                if op == 'NEG':
                    self.emit("PUSHI 0")
                    self.push(src)
                    self.emit("SUB")
                elif op == 'FNEG':
                    self.emit("PUSHF 0.0")
                    self.push(src)
                    self.emit("FSUB")
                else:
                    self.push(src)
                    self.emit(op)
                self.store(instr[1])

            if type == "label":
                self.emit(str(instr[1])+ ":")

            if type == "jump":
                self.emit("JUMP " + str(instr[1]))

            if type == "read":
                self.emit("READ")
                if self.symtab[instr[1]]['type'] == "INTEGER":
                    self.emit("ATOI")
                else:
                    self.emit("ATOF")
                self.store(instr[1])

            if type == "print":             
                for val, typ in instr[1]:
                    self.push(val)
                    if typ == 'INTEGER' or typ == 'LOGICAL':   
                        self.emit("WRITEI")
                    elif typ == 'REAL':    
                        self.emit("WRITEF")   
                    else:                  
                        self.emit("WRITES")
                self.emit("WRITELN")   

            if type == "jz":
                self.push(instr[2])
                self.emit("JZ " + instr[1])


            if type == "load_arr":
                #   ('load_arr',  dst, name, idx)             leitura de array
                self.arrayBase(instr[2])
                self.push(instr[3])
                self.emit("PADD")
                self.emit("LOAD 0")
                self.store(instr[1])

            if type == "store_arr":
                #   ('store_arr', name, idx, val)             escrita em array
                self.arrayBase(instr[1])
                self.push(instr[2])
                self.emit("PADD")
                self.push(instr[3])
                self.emit("STORE 0")

            if type == "read_arr":
                #   ('read_arr',  name, idx)                  leitura de array de stdin
                self.arrayBase(instr[1])
                self.push(instr[2])
                self.emit("PADD")
                self.emit("READ")
                if self.symtab[instr[1]]['type'] == "INTEGER":
                    self.emit("ATOI")
                else:
                    self.emit("ATOF")
                self.emit("STORE 0")

            if type == "call":
                #   ('call',      dst, name, [args])          chamada de função (dst = temp)
                #   ('call',      None, name, [args])         chamada de subrotina
                for arg in instr[3]:
                    self.push(arg)
                if instr[2] in _INTRINSICS:
                    self.emit(_INTRINSICS[instr[2]])
                else:
                    self.emit(f"PUSHA {instr[2]}")
                    self.emit("CALL")
                if instr[1] is not None:
                    self.store(instr[1])

            if type == "return":
                #   ('return',    val_or_None)                retorno
                if instr[1] is not None:
                    self.push(instr[1])
                self.emit("RETURN")
        
        if procedure.kind == "program":
            self.emit("STOP")
