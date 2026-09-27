"""How many `AddOutput basevelocity` outputs are in the shipped maps, and how many carry Z?

WHY THIS EXISTS.  Patch 455's gate refuses to forgive a hopped start while a push carrier is
live, and the size of the problem it is defending against was quoted in a comment as "2004
such outputs across 298 of 1310 shipped maps".  A reviewer could not reproduce that figure,
and neither could I -- it came from a review and was passed on without being regenerated,
which is the rule this repo had just written down: a claim about another file is unverified
until you open that file.  So the figure gets a script, like every other census here.

WHAT IT COUNTS.  Every entity key/value pair in every shipped .bsp whose value contains an
`AddOutput` of `basevelocity`.  Source's output format is
    <OnSomething> <target>,<AddOutput>,<basevelocity X Y Z>,<delay>,<refires>
with 0x1B as the separator on VBSP >= v25 and `,` before that, so both are accepted.

READ IN PAIRS, NOT AS A DICT.  bsplib.parse_ents is lossy: an entity carries MANY keys with
the same name (`OnTrigger` three times is three outputs) and a dict keeps one.  That is
bsplib's own documented warning, and it is the difference between 1706 and 2028 here -- an
18% undercount, which is why this uses read_pairs.

WHAT IT DOES NOT SHOW.  Whether any of them is reachable, whether it overlaps a start zone,
or whether a player can stand in it.  It is a denominator, not a finding.  The Z count is the
one that matters to Patch 455, because a vertical carrier is the case the gate's `vz` term
exists for; `tools/census/pushcensus.py` is the one that asks about start-zone overlap.

RESULT 2026-09-27, over the shipped library:

    1316 .bsp, 0 unreadable
    2029 `AddOutput basevelocity` outputs across 297 maps
    2014 state three components, 1259 of those with a NON-ZERO Z
      15 do not state three
    by carrier event: OnEndTouch 798, OnStartTouch 611, OnJump 583, OnTrigger 20,
                      OnStartTouchAll 11, OnLand 2, OnPass 2, OnEndTouchAll 1,
                      OnLessThan 1

An independent scan by a reviewer, written separately, got 2028/297, 2014 stating three, 1259
non-zero Z and the same event breakdown. The one-output difference in the outer filter is not
chased: everything the gate's argument rests on -- the Z count and the EndTouch count --
agrees exactly.

The EndTouch figure is what Patch 455's dwell is sized against: an OnEndTouch fires
0.06-0.09 s after the last touch, which is four to six packets, and the gate must not grant
inside that window.

THE FIGURE THIS REPLACES WAS WRONG AND WAS MINE.  Patch 455 round 3's comment said "2004
such outputs across 298 of 1310 shipped maps". I took it from a review and shipped it without
regenerating it; 1310 is not today's 1316, and neither the output nor the map count
reproduces. That is the rule I had written into AGENTS.md hours earlier -- a claim about
another file is unverified until you open that file.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib                                              # noqa: E402

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")
MAPS = os.path.join(MOM, "maps")

# ESC (0x1B) on VBSP >= v25, comma before it.  Either way the AddOutput and its value are
# adjacent fields, so a split on both and a look for the pair is enough.
SEP = re.compile(r"[\x1b,]")
BV = re.compile(r"basevelocity\b", re.I)
ADDOUT = re.compile(r"\bAddOutput\b", re.I)


def vec_z(val):
    """-> the Z of a `basevelocity X Y Z` value, or None if it does not state three.

    SPLIT ON THE SEPARATOR FIRST.  The first cut of this used `\\S+` on the whole value and
    got 0 non-zero Z out of 2029, because 0x1B is not whitespace to `\\s`, so `\\S+` ate
    `800\\x1b0\\x1b-1` as one token and float() failed on every output in the library. The
    absurd answer was the only tell; the output COUNT was right all along.
    """
    for field in SEP.split(val):
        f = field.strip()
        if not f.lower().startswith("basevelocity"):
            continue
        parts = f.split()[1:]
        if len(parts) < 3:
            return None
        try:
            return float(parts[2])
        except ValueError:
            return None
    return None


def main():
    if not os.path.isdir(MAPS):
        sys.exit("no maps dir at %s (set MOMENTUM_DIR)" % MAPS)
    files = sorted(f for f in os.listdir(MAPS) if f.lower().endswith(".bsp"))
    if not files:
        sys.exit("no .bsp in %s" % MAPS)

    st = dict(bsp=0, unreadable=0, outputs=0, maps=0, withz=0, noz=0, nonzeroz=0)
    events = {}
    for f in files:
        path = os.path.join(MAPS, f)
        try:
            ents, _models = bsplib.read_pairs(path)
        except Exception:
            ents = None
        if ents is None:
            st["unreadable"] += 1
            continue
        st["bsp"] += 1
        hits = 0
        for pairs in ents:
            for k, v in pairs:
                if not BV.search(v) or not ADDOUT.search(v):
                    continue
                hits += 1
                events[k.lower()] = events.get(k.lower(), 0) + 1
                z = vec_z(v)
                if z is None:
                    st["noz"] += 1
                else:
                    st["withz"] += 1
                    if z != 0.0:
                        st["nonzeroz"] += 1
        if hits:
            st["maps"] += 1
            st["outputs"] += hits

    print("%(bsp)d .bsp, %(unreadable)d unreadable" % st)
    print("%(outputs)d `AddOutput basevelocity` outputs across %(maps)d maps" % st)
    print("  stating three components %(withz)d, of which non-zero Z %(nonzeroz)d"
          % st)
    print("  not stating three        %(noz)d" % st)
    print()
    print("by the event that carries them:")
    for k in sorted(events, key=lambda x: -events[x]):
        print("  %-22s %d" % (k, events[k]))
    end = sum(n for k, n in events.items() if "endtouch" in k)
    print()
    print("  *EndTouch* total        %d -- the figure Patch 455's dwell is sized" % end)
    print("  against, because an OnEndTouch fires 0.06-0.09 s (four to six packets)")
    print("  after the last touch and the gate must not grant inside that window.")
    print()
    print("SELF-CHECK: read in PAIRS, because bsplib.parse_ents is lossy -- an entity may")
    print("carry the same output key many times and a dict keeps one.  If this number is")
    print("close to 1700 rather than 2000, the pair reader is not being used.")


if __name__ == "__main__":
    main()
