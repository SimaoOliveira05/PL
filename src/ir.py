from dataclasses import dataclass, field
from typing import Any


@dataclass
class Copy:
    dst: str
    src: Any


@dataclass
class Binop:
    dst: str
    op: str
    left: Any
    right: Any


@dataclass
class Unary:
    dst: str
    op: str
    src: Any


@dataclass
class Coerce:
    dst: str
    op: str        # e.g. 'ITOF'
    src: Any


@dataclass
class LoadArr:
    dst: str
    name: str
    idx: Any


@dataclass
class StoreArr:
    name: str
    idx: Any
    val: Any


@dataclass
class Read:
    var: str


@dataclass
class ReadArr:
    name: str
    idx: Any


@dataclass
class Print:
    vals: list     # [(val, type_str), ...]


@dataclass
class Label:
    name: str


@dataclass
class Jump:
    label: str


@dataclass
class Jz:
    label: str
    cond: Any


@dataclass
class Call:
    dst: Any       # str se função, None se subrotina
    name: str
    args: list


@dataclass
class Return:
    val: Any       # None se subroutine


INTRINSICS = {
    'MOD':  ('INTEGER', 'MOD'),
    'INT':  ('INTEGER', 'FTOI'),
    'SQRT': ('REAL',    None),
    'ABS':  ('SAME',    None),
    'MAX':  ('SAME',    None),
    'MIN':  ('SAME',    None),
}
