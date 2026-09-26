"""Entity-I/O `Command` parameters, and which of them can inject a second command.

Patch 446.  `SV_IOCommand` (src/server/sv_entities.qc) allow-lists a map's console
command by testing the FIRST space-delimited token against say/echo/print, then hands
the WHOLE string to `localcmd`.  `Cbuf_ExecuteLevel` terminates a command at an
unquoted `;` (engine common/cmd.c:495 and :654), so

    server,Command,echo x;set run_starthop 0

passes the gate and then runs `set run_starthop 0`.  RESTRICT_INSECURE is 30 against a
default rcon_level of 20, so anything registered without an explicit restriction
executes.  `run_starthop` is read live every packet, so one map switches the whole
hopped-start rule off for everyone -- through the door Patch 445 cites as the reason
its design is safe.  Found by two independent reviewers in 445's round 6.

THE QUESTION THIS ANSWERS, and it decides the FIX rather than confirming the bug:
refusing any parameter containing `;` is the simplest sound fix, and its cost is
however many shipped maps legitimately put a `;` in their say text.  If that count is
0 the refusal is free and provably so; if it is large the fix has to quote instead,
which is more code and more ways to be wrong.  Measure first.

READ tools/census/README.md's grading section before quoting any number.  This census
does NOT have the AABB problem -- it reads strings, not boxes -- but it has its own:
Source's entity-I/O value is `target,Input,param,delay,times`, so a param containing a
comma is SPLIT by the format itself.  That is why `raw` is counted beside `param`: the
whole value is scanned as well, so a `;` hiding past a comma is still seen.

RESULT 2026-09-27, filled in from the run below.
"""
import os
import sys

import bsplib

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")
MAPS = os.path.join(MOM, "maps")

# What SV_IOCommand lets through today.
ALLOWED = ("say", "echo", "print")
# What Cbuf treats as a command terminator, plus the quote that changes its mind.
INJECT = (";", "\n", "\r")


def io_commands(ents):
    """-> list of (classname, key, rawvalue, param) for every Command output."""
    out = []
    for e in ents:
        cn = (e.get("classname") or "").lower()
        for k, v in e.items():
            if not isinstance(v, str) or "," not in v:
                continue
            parts = v.split(",")
            if len(parts) < 3:
                continue
            if parts[1].strip().lower() != "command":
                continue
            # The param is parts[2], but the format's own comma split may have cut it.
            # Keep both: the declared param and the raw value.
            out.append((cn, k, v, parts[2]))
    return out


def first_token(s):
    s = s.strip()
    sp = s.find(" ")
    return (s if sp < 0 else s[:sp]).lower()


def main():
    if not os.path.isdir(MAPS):
        sys.exit("no maps dir at %s (set MOMENTUM_DIR)" % MAPS)
    bsps = sorted(f for f in os.listdir(MAPS) if f.lower().endswith(".bsp"))

    st = dict(total=len(bsps), scanned=0, unreadable=0,
              cmd_maps=0, cmd_rows=0, allowed=0, refused=0,
              inj_param=0, inj_raw=0, inj_allowed=0, quote=0)
    inject_rows, verbs = [], {}

    for f in bsps:
        try:
            ents, _ = bsplib.read(os.path.join(MAPS, f))
        except Exception:
            st["unreadable"] += 1
            continue
        if ents is None:
            st["unreadable"] += 1
            continue
        st["scanned"] += 1

        rows = io_commands(ents)
        if not rows:
            continue
        st["cmd_maps"] += 1
        name = os.path.splitext(f)[0]

        for cn, k, raw, param in rows:
            st["cmd_rows"] += 1
            w = first_token(param)
            verbs[w] = verbs.get(w, 0) + 1
            ok = w in ALLOWED
            st["allowed" if ok else "refused"] += 1

            hit_p = any(c in param for c in INJECT)
            hit_r = any(c in raw for c in INJECT)
            if hit_p:
                st["inj_param"] += 1
            if hit_r:
                st["inj_raw"] += 1
            if '"' in param:
                st["quote"] += 1
            # THE ONE THAT MATTERS: a parameter that the gate ADMITS and that also
            # carries a terminator.  Anything the gate already refuses is not a
            # bypass, whatever it contains.
            if ok and hit_r:
                st["inj_allowed"] += 1
                inject_rows.append((name, cn, k, raw))

    print("bsp %(total)d  scanned %(scanned)d  unreadable %(unreadable)d" % st)
    print("maps with a Command output: %(cmd_maps)d   rows: %(cmd_rows)d"
          "   (allow-listed %(allowed)d, already refused %(refused)d)" % st)
    print()
    print("rows carrying a Cbuf terminator (; CR LF):")
    print("    in the declared param: %(inj_param)d" % st)
    print("    anywhere in the value: %(inj_raw)d" % st)
    print("    ...AND allow-listed:   %(inj_allowed)d   <- the only bypass count"
          % st)
    print("rows containing a double quote:      %(quote)d" % st)
    print()
    print("SELF-CHECK -- a filter that never fires proves nothing.  If `cmd_rows` is 0")
    print("the corpus has no Command output at all and every zero above is vacuous.")
    print("verbs seen, most common first (proves the param was really parsed):")
    for w, n in sorted(verbs.items(), key=lambda kv: -kv[1])[:12]:
        print("    %-22s %d%s" % (w or "<empty>", n,
                                  "   [allow-listed]" if w in ALLOWED else ""))

    if inject_rows:
        print()
        print("--- ALLOW-LISTED ROWS THAT CAN INJECT ---")
        for r in inject_rows[:40]:
            print("  %-28s %-22s %-18s %s" % (r[0], r[1], r[2][:18], r[3][:90]))


if __name__ == "__main__":
    main()
