from dataclasses import dataclass
from typing import Any


@dataclass
class Procedure:
    name: str
    symtab: dict
    instructions: list
    is_function: bool
    return_type: str | None
    kind: str

    def __init__(self, symtab, name, is_function, return_type, kind):
        self.name = name
        self.symtab = symtab
        self.is_function = is_function
        self.return_type = return_type
        self.instructions = []
        self.kind = kind

@dataclass
class IRProgram:
    procedures: list[Procedure]

    def __init__(self, procedures):
        self.procedures = procedures

    def __iter__(self):
        return iter(self.procedures)


def is_temp(name) -> bool:
    """Returns True if name is a compiler-generated temporary (e.g. 't0', 't12')."""
    return isinstance(name, str) and name.startswith('t') and name[1:].isdigit()


def _sub(val, m):
    """Returns the copy-propagation replacement for val if one exists, otherwise val."""
    if isinstance(val, str) and val in m:
        return m[val]
    return val


@dataclass
class Copy:
    dst: str
    src: Any

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        if is_temp(self.src):
            result.add(self.src)
        return result

    def substitute(self, m):
        return Copy(self.dst, _sub(self.src, m))


@dataclass
class Binop:
    dst: str
    op: str
    left: Any
    right: Any

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        if is_temp(self.left):
            result.add(self.left)
        if is_temp(self.right):
            result.add(self.right)
        return result

    def substitute(self, m):
        return Binop(self.dst, self.op, _sub(self.left, m), _sub(self.right, m))


@dataclass
class Unary:
    dst: str
    op: str
    src: Any

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        if is_temp(self.src):
            result.add(self.src)
        return result

    def substitute(self, m):
        return Unary(self.dst, self.op, _sub(self.src, m))


@dataclass
class Coerce:
    dst: str
    op: str        # e.g. 'ITOF'
    src: Any

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        if is_temp(self.src):
            result.add(self.src)
        return result

    def substitute(self, m):
        return Coerce(self.dst, self.op, _sub(self.src, m))


@dataclass
class LoadArr:
    dst: str
    name: str
    idx: Any

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        if is_temp(self.idx):
            result.add(self.idx)
        return result

    def substitute(self, m):
        return LoadArr(self.dst, self.name, _sub(self.idx, m))


@dataclass
class StoreArr:
    name: str
    idx: Any
    val: Any

    def get_dst(self):
        return None

    def uses(self):
        result = set()
        if is_temp(self.idx):
            result.add(self.idx)
        if is_temp(self.val):
            result.add(self.val)
        return result

    def substitute(self, m):
        return StoreArr(self.name, _sub(self.idx, m), _sub(self.val, m))


@dataclass
class Read:
    var: str

    def get_dst(self):
        return None

    def uses(self):
        return set()

    def substitute(self, m):
        return self


@dataclass
class ReadArr:
    name: str
    idx: Any

    def get_dst(self):
        return None

    def uses(self):
        result = set()
        if is_temp(self.idx):
            result.add(self.idx)
        return result

    def substitute(self, m):
        return ReadArr(self.name, _sub(self.idx, m))


@dataclass
class Print:
    vals: list     # [(val, type_str), ...]

    def get_dst(self):
        return None

    def uses(self):
        result = set()
        for val, _ in self.vals:
            if is_temp(val):
                result.add(val)
        return result

    def substitute(self, m):
        new_vals = []
        for val, t in self.vals:
            new_vals.append((_sub(val, m), t))
        return Print(new_vals)


@dataclass
class Label:
    name: str

    def get_dst(self):
        return None

    def uses(self):
        return set()

    def substitute(self, m):
        return self


@dataclass
class Jump:
    label: str

    def get_dst(self):
        return None

    def uses(self):
        return set()

    def substitute(self, m):
        return self


@dataclass
class Jz:
    label: str
    cond: Any

    def get_dst(self):
        return None

    def uses(self):
        result = set()
        if is_temp(self.cond):
            result.add(self.cond)
        return result

    def substitute(self, m):
        return Jz(self.label, _sub(self.cond, m))


@dataclass
class Call:
    dst: Any       # str se função, None se subrotina
    name: str
    args: list

    def get_dst(self):
        return self.dst

    def uses(self):
        result = set()
        for arg in self.args:
            if is_temp(arg):
                result.add(arg)
        return result

    def substitute(self, m):
        new_args = []
        for arg in self.args:
            new_args.append(_sub(arg, m))
        return Call(self.dst, self.name, new_args)


@dataclass
class Return:
    val: Any       # None se subroutine

    def get_dst(self):
        return None

    def uses(self):
        result = set()
        if is_temp(self.val):
            result.add(self.val)
        return result

    def substitute(self, m):
        return Return(_sub(self.val, m))


INTRINSICS = {
    'MOD':  ('INTEGER', 'MOD'),
    'INT':  ('INTEGER', 'FTOI'),
    'SQRT': ('REAL',    None),
    'ABS':  ('SAME',    None),
    'MAX':  ('SAME',    None),
    'MIN':  ('SAME',    None),
}

# Subset with a direct VM opcode, used by codegen
_INTRINSICS = {name: ops[1] for name, ops in INTRINSICS.items() if ops[1] is not None}
