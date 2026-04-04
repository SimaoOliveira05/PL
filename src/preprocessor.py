import re

def upper_outside_strings(code):
    """
    Converts everything to uppercase except content inside single quotes.
    Fortran 77 is case-insensitive, but string literals must be preserved.
    """
    parts = re.split(r"('[^']*')", code)
    return ''.join(p if p.startswith("'") else p.upper() for p in parts)


def preprocess(file):
    """
    Reads a Fortran 77 fixed-format file and returns
    a list of logical lines ready for the lexer.
    Each item is a dictionary:
      { 'label': '10' | None, 'code': 'CONTINUE', 'physical_line': 42 }
    """
    logical_lines = []
    current_line = None
    current_label = None
    start_physical_line = None

    for num, physical_line in enumerate(file, start=1):
        # Normalize: remove '\n' and guarantee 72 characters
        line = physical_line.rstrip('\n')
        line = line.ljust(72)

        col1 = line[0]
        col6 = line[5]
        cols_1_5 = line[0:5]
        cols_7_72 = line[6:72].strip()

        # ── Rule 1: comment ──────────────────────────────────────────
        if col1 in ('C', 'c', '*'):
            continue

        # ── Rule 2: blank line ───────────────────────────────────────
        if cols_7_72 == '':
            continue

        # ── Rule 3: continuation line ────────────────────────────────
        if col6 not in (' ', '0'):
            if current_line is None:
                raise SyntaxError(
                    f"Line {num}: continuation without a previous line"
                )
            current_line += ' ' + upper_outside_strings(cols_7_72)
            continue

        # ── Rule 4: normal line ──────────────────────────────────────
        if current_line is not None:
            logical_lines.append({
                'label':         current_label,
                'code':          current_line,
                'physical_line': start_physical_line
            })

        current_label = cols_1_5.strip() or None
        current_line = upper_outside_strings(cols_7_72)
        start_physical_line = num

    # Don't forget the last logical line
    if current_line is not None:
        logical_lines.append({
            'label':         current_label,
            'code':          current_line,
            'physical_line': start_physical_line
        })
    return logical_lines
