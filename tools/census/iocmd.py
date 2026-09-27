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

RESULT 2026-09-27, 1316 bsps, 0 unreadable, AFTER round 7 fixed this tool's two
blind spots (see io_commands).  The first published run of this census was roughly HALF
of every count below; the conclusion was unchanged by the correction.

    301 maps carry a Command output, 1438 rows.
    194 allow-listed as the GATE sees the verb (201 under a strip+lower matcher).
    1237 already refused on the verb.
    144 rows on 34 maps are ESC-separated -- invisible to the pre-round-7 parser.

    13 rows carry a Cbuf terminator (; CR LF), and NONE OF THE THIRTEEN IS
    ALLOW-LISTED: every one begins sv_cheats / sv_airaccelerate / sv_maxvelocity, so
    all thirteen were already refused on their verb.  0 rows contain a quote.  0
    contain `$` or `%`.

SO THE REFUSAL IS FREE, and that is the number the fix rests on.  Verb histogram, which
is the self-check that the params were really parsed: play 303, say 186, sv_airaccelerate
141, playgamesound 124, sv_maxvelocity 114, r_screenoverlay 93, sv_enablebunnyhopping 65
-- 25 rows try `sv_cheats` outright and the allow-list has always refused them.
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


ESC = "\x1b"


def io_commands(pairs):
    """-> list of (classname, key, rawvalue, param) for every Command output.

    TWO BUGS FIXED HERE AFTER A REVIEW RE-CENSUSED THE SAME QUESTION AND GOT ROUGHLY
    DOUBLE.  Both made this tool blind to whole classes of row rather than merely
    imprecise, which is the repo's own "a filter that never fires" trap one level up --
    in the PARSER, with a self-check scoped to the same blind spot so it could not
    notice.

      1  IT TOOK A DICT.  bsplib.parse_ents builds `{key: value}`, so an entity with
         several outputs under one key name kept only the LAST -- and Source entities
         repeat output keys routinely.  Measured: 450 of 1438 rows lost.  It now takes
         bsplib.parse_ents_pairs, which keeps every occurrence.
      2  IT ASSUMED A COMMA.  VBSP >= v25 separates the I/O record with 0x1B ESC, and
         the mod's own reader PICKS THE SEPARATOR PER VALUE (sv_entities.qc:4071:
         `if (strstrofs(v, vbsp_io_esc, 0) >= 0) sep = vbsp_io_esc;`).  The old
         `if "," not in v: continue` skipped every ESC row -- 144 rows on 34 maps,
         including bhop_arcane, the map the gate's own essay names as the allow-list's
         legitimate customer.  This now chooses the separator the same way the QC does.
    """
    out = []
    for ent in pairs:
        cn = ""
        for k, v in ent:
            if k == "classname":
                cn = v.lower()
        for k, v in ent:
            sep = ESC if ESC in v else ","
            if sep not in v:
                continue
            parts = v.split(sep)
            if len(parts) < 3:
                continue
            if parts[1].strip().lower() != "command":
                continue
            out.append((cn, k, v, parts[2]))
    return out


def first_token(s, exact=False):
    """The verb.

    `exact=True` is what the SHIPPED GATE sees: SV_IOCommand does `strstrofs(cmd, " ")`
    then compares with `==` against the literals -- NO strip and NO lowercase.  The lax
    form is kept beside it because the difference is a number worth reporting: a review
    measured 101 lax against 94 exact, i.e. seven rows this tool called "allow-listed"
    are actually refused on a leading space or a capital.  The looseness is conservative
    for the claim the census is used for -- 0 lax implies 0 exact -- but quoting the lax
    number as "the allow-list working" overstates it.
    """
    if exact:
        sp = s.find(" ")
        return s if sp < 0 else s[:sp]
    s = s.strip()
    sp = s.find(" ")
    return (s if sp < 0 else s[:sp]).lower()


def main():
    if not os.path.isdir(MAPS):
        sys.exit("no maps dir at %s (set MOMENTUM_DIR)" % MAPS)
    bsps = sorted(f for f in os.listdir(MAPS) if f.lower().endswith(".bsp"))

    st = dict(total=len(bsps), scanned=0, unreadable=0,
              cmd_maps=0, cmd_rows=0, allowed=0, allowed_exact=0, refused=0,
              inj_param=0, inj_raw=0, inj_allowed=0, quote=0, dollar=0,
              esc_rows=0, esc_maps=0)
    inject_rows, verbs = [], {}

    for f in bsps:
        try:
            ents, _ = bsplib.read_pairs(os.path.join(MAPS, f))
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
        esc_here = False
        for cn, k, raw, param in rows:
            st["cmd_rows"] += 1
            if ESC in raw:
                st["esc_rows"] += 1
                esc_here = True
            w = first_token(param)
            verbs[w] = verbs.get(w, 0) + 1
            ok = w in ALLOWED
            st["allowed" if ok else "refused"] += 1
            # What the SHIPPED gate admits, which is stricter than `w`.
            if first_token(param, exact=True) in ALLOWED:
                st["allowed_exact"] += 1

            hit_p = any(c in param for c in INJECT)
            hit_r = any(c in raw for c in INJECT)
            if hit_p:
                st["inj_param"] += 1
            if hit_r:
                st["inj_raw"] += 1
            if '"' in param:
                st["quote"] += 1
            # `$` is a SEPARATE class from the terminators: Cmd_ExpandCvar interpolates
            # `$cvar` into the text AFTER the Cbuf split, so it cannot start a second
            # command -- but it can read a cvar out, and `rcon_password` is expandable at
            # this exec level.  Counted so the cost of refusing it is known rather than
            # guessed.  Round 7, lens A; READ IN THE ENGINE, NOT MEASURED IN A RUN.
            if "$" in param or "%" in param:
                st["dollar"] += 1
            # THE ONE THAT MATTERS: a parameter that the gate ADMITS and that also
            # carries a terminator.  Anything the gate already refuses is not a
            # bypass, whatever it contains.
            if ok and hit_r:
                st["inj_allowed"] += 1
                inject_rows.append((name, cn, k, raw))
        if esc_here:
            st["esc_maps"] += 1

    print("bsp %(total)d  scanned %(scanned)d  unreadable %(unreadable)d" % st)
    print("maps with a Command output: %(cmd_maps)d   rows: %(cmd_rows)d" % st)
    print("    allow-listed, lax matcher (strip+lower): %(allowed)d" % st)
    print("    allow-listed, AS THE GATE SEES IT:       %(allowed_exact)d"
          "   <- quote this one" % st)
    print("    already refused on the verb:             %(refused)d" % st)
    print("    ESC-separated (invisible to the pre-round-7 tool): %(esc_rows)d rows on "
          "%(esc_maps)d maps" % st)
    print()
    print("rows carrying a Cbuf terminator (; CR LF):")
    print("    in the declared param: %(inj_param)d" % st)
    print("    anywhere in the value: %(inj_raw)d" % st)
    print("    ...AND allow-listed:   %(inj_allowed)d   <- the only bypass count"
          % st)
    print("rows containing a double quote:      %(quote)d" % st)
    print("rows containing $ or %% (cvar expansion, a different class): %(dollar)d" % st)
    print()
    print("SELF-CHECK -- a filter that never fires proves nothing, AND NEITHER DOES A")
    print("PARSER THAT CANNOT SEE A CLASS OF ROW.  Round 7 found this tool blind twice")
    print("over (a dict that dropped repeated keys, and an assumed comma separator),")
    print("with a self-check scoped to the same blind spot.  So the ESC count above is")
    print("part of the self-check now: if it is 0 on a corpus this size, suspect the")
    print("parser before believing the number.")
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
