"""P1545: QC assignments (= and |= += ...) whose right side has a top-level && or ||. id's table, which
fteqcc keeps, binds `=` tighter, so `x = a && b` stores a. Statements are split on ; { } across lines,
comments and strings stripped; for-header increments and initialisers (whole expressions) are excluded.
Usage: python tools/p1545precscan.py src     (prints file:line per site, the count on stderr)"""
import re, sys, pathlib


def clean(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != '\n':
                j += 2 if text[j] == '\\' else 1
            out.append('""'); i = j + 1; continue
        if text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            end = n if j < 0 else j + 2
            out.append('\n' * text.count('\n', i, end))
            i = end
            continue
        out.append(c); i += 1
    return ''.join(out)


def first_assign(s):
    d = 0
    for idx, ch in enumerate(s):
        if ch in '([': d += 1
        elif ch in ')]': d -= 1
        elif ch == '=' and d == 0:
            prev = s[idx - 1] if idx else ''
            nxt = s[idx + 1] if idx + 1 < len(s) else ''
            if nxt != '=' and prev not in '=!<>':
                return idx
    return -1


def top_logic(rhs):
    d = 0
    for idx in range(len(rhs)):
        ch = rhs[idx]
        if ch in '([': d += 1
        elif ch in ')]':
            d -= 1
            if d < 0:
                return False             # a for-header's increment: the ')' closes it
        elif d == 0 and rhs.startswith(('&&', '||'), idx):
            return True
    return False


root = pathlib.Path(sys.argv[1])
hits = []
for f in sorted(root.rglob('*.qc')) + sorted(root.rglob('*.qh')):
    text = clean(f.read_text(encoding='utf-8', errors='replace'))
    start = 0
    for m in re.finditer(r'[;{}]', text):
        stmt, s0 = text[start:m.start()], start
        start = m.end()
        s = stmt.strip()
        while True:                      # drop leading if (...) / while (...) / else headers
            k = re.match(r'^(if|while|else)\b\s*', s)
            if not k:
                break
            s = s[k.end():]
            if s.startswith('('):
                d = 0
                for idx, ch in enumerate(s):
                    if ch == '(': d += 1
                    elif ch == ')':
                        d -= 1
                        if d == 0:
                            s = s[idx + 1:].strip(); break
        if not s or re.match(r'^(for|return|do)\b', s):
            continue
        if re.match(r'^(local\s+)?(float|vector|string|entity|int|__variant)\b', s):
            continue                     # an initialiser is one whole expression (asm probe, P1545)
        eq = first_assign(s)
        if eq >= 0 and top_logic(s[eq + 1:]):
            ln = text.count('\n', 0, s0 + stmt.find(s[:eq])) + 1
            hits.append(f"{f.relative_to(root)}:{ln}: {' '.join(s.split())[:150]}")
print('\n'.join(hits))
print(f"-- {len(hits)} sites", file=sys.stderr)
