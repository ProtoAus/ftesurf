#!/usr/bin/env python3
"""
test_injrn.py -- the falsifier for cl_replay.qc's Rec_JrnIdentReport (Patch 486).

    python tools/test_injrn.py [path/to/cl_replay.qc]

No QC VM runs outside the game, so this EXECUTES THE FUNCTION'S OWN SOURCE: a
narrow QC-to-Python translation of exactly the statements it uses (locals,
assignments, if/return, two calls), which raises on anything else rather than
guessing.  Rec_ViewInit's seed and Rec_ViewFrame's two call sites are read from
the same file, so reverting either fix there fails a named check here.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
QC = os.path.join(os.path.dirname(HERE), "src", "client", "cl_replay.qc")
DEFS = os.path.join(os.path.dirname(HERE), "src", "shared", "sh_defs.qc")

CHECKS = 0
FAILED = []


def check(cond, what):
    global CHECKS
    CHECKS += 1
    print("  %s  %s" % ("ok  " if cond else "FAIL", what))
    if not cond:
        FAILED.append(what)


# ---------------------------------------------------------------- source ----
def strip_comments(src):
    out = re.sub(r'("(?:\\.|[^"\\])*")|/\*.*?\*/|//[^\n]*',
                 lambda m: m.group(1) or " ", src, flags=re.S)
    return out


def braced(src, start):
    """The text between the first '{' at or after `start` and its match."""
    i = src.index("{", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
    raise ValueError("unbalanced braces")


def function(src, name):
    m = re.search(r"\bvoid\s*\(([^)]*)\)\s*%s\s*=" % name, src)
    if not m:
        raise ValueError("no definition of %s" % name)
    params = [p.split()[-1] for p in m.group(1).split(",") if p.strip()]
    return params, braced(src, m.end())


TOK = re.compile(r'\s*("(?:\\.|[^"\\])*"|&&|\|\||==|!=|<=|>=|[A-Za-z_]\w*|'
                 r'\d+\.?\d*|[-+*/<>=!(),;{}])')


def tokens(text):
    out, i = [], 0
    text = text.rstrip()
    while i < len(text):
        m = TOK.match(text, i)
        if not m:
            raise ValueError("cannot tokenise %r" % text[i:i + 20])
        out.append(m.group(1))
        i = m.end()
    return out


def expr(toks):
    py = []
    k = 0
    while k < len(toks):
        t = toks[k]
        if t == "&&":
            py.append("and")
        elif t == "||":
            py.append("or")
        elif t == "!":
            nxt = toks[k + 1] if k + 1 < len(toks) else ""
            if not re.match(r"[A-Za-z_]\w*$", nxt):
                raise ValueError("'!' before %r is outside this translator" % nxt)
            py.append("(not %s)" % nxt)
            k += 1
        elif t == "TRUE":
            py.append("1.0")
        elif t == "FALSE":
            py.append("0.0")
        else:
            py.append(t)
        k += 1
    return " ".join(py)


def translate(name, params, body, inout):
    """-> (python source, globals it assigns)."""
    toks = tokens(body)
    lines, local, assigned = [], set(params), set()

    def statement(i, ind):
        t = toks[i]
        if t == "local":
            j = toks.index(";", i)
            names = [x for x in toks[i + 2:j] if x != ","]
            local.update(names)
            lines.append(ind + "%s = 0.0" % " = ".join(names))
            return j + 1
        if t == "if":
            depth, j = 0, i + 1
            while True:
                depth += toks[j] == "("
                depth -= toks[j] == ")"
                if depth == 0:
                    break
                j += 1
            lines.append(ind + "if %s:" % expr(toks[i + 2:j]))
            return statement(j + 1, ind + "    ")
        if t == "return":
            if toks[i + 1] != ";":
                raise ValueError("a valued return is outside this translator")
            lines.append(ind + "return")
            return i + 2
        j = toks.index(";", i)
        st = toks[i:j]
        if len(st) > 2 and st[1] == "=" and st[2] != "=":
            rhs = st[2:]
            target = st[0]
            if target not in local:
                assigned.add(target)
            if rhs[0] in inout and rhs[1] == "(":
                args, cur, depth = [], [], 0
                for x in rhs[2:-1]:
                    if x == "," and depth == 0:
                        args.append(cur)
                        cur = []
                        continue
                    depth += (x == "(") - (x == ")")
                    cur.append(x)
                args.append(cur)
                out = args[inout[rhs[0]]]
                if len(out) != 1:
                    raise ValueError("__inout argument is not a name")
                lines.append(ind + "%s, %s = %s" % (target, out[0], expr(rhs)))
            else:
                lines.append(ind + "%s = %s" % (target, expr(rhs)))
        elif len(st) > 2 and st[1] == "(" and st[-1] == ")":
            lines.append(ind + expr(st))
        else:
            raise ValueError("statement outside this translator: %r" % " ".join(st))
        return j + 1

    i = 0
    while i < len(toks):
        i = statement(i, "    ")
    head = ["def %s(%s):" % (name, ", ".join(params))]
    glob = sorted(assigned - local)
    if glob:
        head.append("    global " + ", ".join(glob))
    return "\n".join(head + lines) + "\n", glob


# ------------------------------------------------------------ the harness ----
class Client(object):
    """One CSQC VM: fresh globals, Rec_ViewInit's seed, and an engine whose five
    in_jrn484_* cvars the arm sets (None = a pre-484 engine without them)."""

    def __init__(self, src, defs):
        s = strip_comments(src)
        params, body = function(s, "Rec_JrnIdentReport")
        sig = re.search(r"float\s*\(([^)]*)\)\s*Rec_InputCvar\s*=", s)
        inout = {"Rec_InputCvar": [k for k, p in enumerate(sig.group(1).split(","))
                                   if "__inout" in p][0]}
        code, glob = translate("Rec_JrnIdentReport", params, body, inout)
        self.code = code
        self.cvars = None
        self.sent = []
        ijh = re.search(r"#define\s+IJH_IDENT\s+(\d+)", defs)
        self.ns = {"IJH_IDENT": float(ijh.group(1)), "cltime": 0.0,
                   "Rec_InputCvar": self._cvar, "sendevent": self._send}
        for g in glob:
            self.ns[g] = 0.0                    # a fresh VM zeroes its globals
        exec(code, self.ns)
        _p, init = function(s, "Rec_ViewInit")
        seed = re.search(r"\brec_rp_ijsent\s*=\s*([^;]+);", init)
        self.seeded = seed is not None
        if seed:
            self.ns["rec_rp_ijsent"] = eval(expr(tokens(seed.group(1))), dict(self.ns))
        # the two call sites in Rec_ViewFrame: the per-frame one, and the one in
        # the run-end branch (`else if (rec_rp_wasrec)`)
        _p, frame = function(s, "Rec_ViewFrame")
        calls = [(m.start(), m.group(1)) for m in
                 re.finditer(r"\bRec_JrnIdentReport\s*\(([^)]*)\)\s*;", frame)]
        edge = frame.find("else if (rec_rp_wasrec)")
        end_block = braced(frame, edge) if edge >= 0 else ""
        self.args_frame = [c for c in calls if edge < 0 or c[0] < edge]
        self.args_end = [a for _, a in re.findall(r"(\bRec_JrnIdentReport\s*\(([^)]*)\)\s*;)",
                                                  end_block)]

    def _cvar(self, name, bit, have):
        if self.cvars is None or name not in self.cvars:
            return 0.0, have
        return float(self.cvars[name]), float(int(have) | int(bit))

    def _send(self, ev, types, *args):
        self.sent.append((self.ns["cltime"], ev, types) + tuple(args))

    def call(self, argtext, t):
        self.ns["cltime"] = t
        args = [eval(expr(tokens(a)), dict(self.ns)) for a in argtext.split(",")
                if a.strip()]
        self.ns["Rec_JrnIdentReport"](*args)


def counters(frames, ghosts=0, viol=0, bad=0, skip=0):
    return {"in_jrn484_frames": frames, "in_jrn484_ghosts": ghosts,
            "in_jrn484_violations": viol, "in_jrn484_badframes": bad,
            "in_jrn484_skipped": skip}


def main(argv):
    path = argv[0] if argv else QC
    src = open(path, encoding="utf-8").read()
    defs = open(DEFS, encoding="utf-8").read()
    print("test_injrn.py -- Rec_JrnIdentReport executed from %s\n"
          % os.path.relpath(path, os.path.dirname(HERE)))

    c = Client(src, defs)
    check(c.seeded, "Rec_ViewInit seeds rec_rp_ijsent")
    check(len(c.args_frame) == 1,
          "Rec_ViewFrame reports once per frame outside the run-end branch (%d)"
          % len(c.args_frame))
    frame_args = c.args_frame[0][1] if c.args_frame else ""

    # 1. FIX 5: the first report always goes out -- on a pre-484 engine all five
    # read 0, equal to the zeroed cache, which is the case -1 skipped.
    for k in range(5):
        c.call(frame_args, k / 60.0)
    check(len(c.sent) == 1,
          "pre-484 engine (no counters): the first report goes out, once (%d sent)"
          % len(c.sent))
    check(c.sent[:1] and c.sent[0][3:] == (0.0,) * 6,
          "...carrying have 0 and five zeros (%s)" % (c.sent[:1] or "nothing"))

    c = Client(src, defs)
    c.cvars = counters(-1, -1, -1, -1, -1)
    for k in range(5):
        c.call(frame_args, k / 60.0)
    check(len(c.sent) == 1 and c.sent[0][4] == -1.0,
          "484 engine before any journal: -1 goes out once, unnormalised (%s)"
          % [s[3:] for s in c.sent])

    # 2. FIX 4: the counters move on every governed frame of a run.  300 fps for
    # 9.5 s must not be 2850 reliable messages.
    c = Client(src, defs)
    fps, n = 300.0, 2850
    for k in range(n):
        c.cvars = counters(k, bad=k // 100, viol=k // 100)
        c.call(frame_args, k / fps)
    gaps = [b[0] - a[0] for a, b in zip(c.sent, c.sent[1:])]
    check(len(c.sent) <= 10,
          "a 9.5 s run at 300 fps: at most one report a second (%d sent, %d bytes "
          "of reliable buffer)" % (len(c.sent), 38 * len(c.sent)))
    check(len(c.sent) >= 9,
          "...and it still reports while they move (%d sent)" % len(c.sent))
    check(not gaps or min(gaps) >= 1.0 - 1e-9,
          "...never two within a second (closest %.4f s)" % (min(gaps) if gaps else 0))

    # 3. The run end forces one past the throttle, so the server holds the
    # counters when the receipt lands.
    check(len(c.args_end) == 1,
          "the run-end branch sends a report (%d call(s) there)" % len(c.args_end))
    t_end = n / fps                         # the next frame
    check(c.sent and t_end < c.sent[-1][0] + 1.0,
          "precondition: the edge falls inside the throttle window (%.3f s after "
          "the last report)" % (t_end - c.sent[-1][0] if c.sent else -1))
    final = counters(n + 7, bad=99, viol=98)
    c.cvars = final
    before = len(c.sent)
    c.call(frame_args, t_end)              # the per-frame call, throttled
    for a in c.args_end:
        c.call(a, t_end)
    check(len(c.sent) == before + 1 and c.sent[-1][0] == t_end,
          "...at the edge itself, inside the throttle window (%d new)"
          % (len(c.sent) - before))
    check(c.sent[-1][4:] == (float(n + 7), 0.0, 98.0, 99.0, 0.0),
          "...carrying the counters as the run ended (%s)" % (c.sent[-1][4:],))
    del final

    # 4. The journal closes a frame later, so one more change follows; it must
    # still arrive once the counters stop moving -- the trailing send.
    last = counters(n + 8, bad=99, viol=98)
    c.cvars = last
    t = t_end
    for k in range(1, 2 * int(fps)):
        t = t_end + k / fps
        c.call(frame_args, t)
    tail = c.sent[-1]
    check(tail[4] == float(n + 8),
          "the last change after the edge still reaches the server (frames %g)"
          % tail[4])
    check(tail[0] - t_end <= 1.0 + 1.0 / fps,
          "...within a second of the edge (%.3f s)" % (tail[0] - t_end))
    check(len([s for s in c.sent if s[0] > t_end]) == 1,
          "...in exactly one more report, not one a frame")

    print("\n%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
