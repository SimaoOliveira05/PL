# Intrinsic functions known to the compiler.
#
# Each entry: name → (return_type, vm_op)
#   return_type : 'INTEGER' | 'REAL' | 'SAME'  ('SAME' = type of first arg)
#   vm_op       : VM instruction string, or None → emit PUSHA name + CALL

INTRINSICS = {
    'MOD':  ('INTEGER', 'MOD'),
    'INT':  ('INTEGER', 'FTOI'),
    'SQRT': ('REAL',    None),
    'ABS':  ('SAME',    None),
    'MAX':  ('SAME',    None),
    'MIN':  ('SAME',    None),
}
