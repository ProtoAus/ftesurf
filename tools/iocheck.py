#!/usr/bin/env python3
"""
iocheck.py -- hold the entity-I/O output registry to its own promise.

WHY THIS EXISTS.  sv_entities.qc keeps a hand-maintained list of every output
name something actually fires, in SV_IOOutputKnown.  SV_EntityIOBuild tests a
map's declared outputs against it and warns "nothing fires 'X'" for the rest,
so the list is what makes that warning mean anything.  Its own comment has
always said the quiet part out loud:

    "THIS LIST IS HAND-MAINTAINED AND NOTHING TIES IT TO THE FIRE SITES.
     Adding a SV_FireOutput call without adding its name here makes the check
     cry wolf; adding a name here without a fire site makes it lie the other
     way and is worse, because the silence then reads as 'implemented'."

It was right to worry.  Before build 63 the comment also claimed "there are as
many names here as there are SV_FireOutput call sites", and that had already
stopped being true -- 19 names against 23 call sites, because OnStartTouch fires
from three sites, OnEndTouch from three and OnTimer from two.  Nobody noticed,
because the only check was reading eight lines of &&-joined != tests by eye.

Build 63 roughly doubles the name count.  This script replaces the eye.

WHAT IT CHECKS, which is the weaker but actually-true invariant:

    every name in SV_IOOutputKnown has at least one SV_FireOutput call site
    every SV_FireOutput call site's name is in SV_IOOutputKnown

THE ONE THING IT CANNOT SEE is a fire site whose name is not a literal.
logic_case is the only one: SV_IOCasePick and SV_IOCaseValue fire through
SV_IOCaseName(i), which builds "oncase01".."oncase16" at runtime, and
SV_IOOutputKnown matches them with a prefix test rather than sixteen literals.
Both halves are listed under KNOWN_DYNAMIC below so that adding a second
computed family forces someone to come back here and say so.

Usage:
    python iocheck.py                 # checks the tree's sv_entities.qc
    python iocheck.py <path.qc>
Exit code is 1 on any mismatch, so it can gate a build.
"""

import os
import re
import sys

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "src", "server", "sv_entities.qc")

# Output names fired through a computed string rather than a literal, with the
# SV_IOOutputKnown arm that covers them.  Anything added here needs a comment
# saying which function builds the name.
KNOWN_DYNAMIC = {
    # SV_IOCaseName() -> "oncase01".."oncase16", fired by SV_IOCasePick and
    # SV_IOCaseValue; matched by the strlen/substring prefix arm.
    "oncase%02d" % i: "SV_IOCaseName" for i in range(1, 17)
}

FIRE = re.compile(r'SV_FireOutput\s*\([^,]+,\s*"([A-Za-z0-9_]+)"')
KNOWN = re.compile(r'lk\s*==\s*"([a-z0-9_]+)"')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    try:
        src = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError as e:
        print("iocheck: cannot read %s: %s" % (path, e))
        return 2

    fired = {}
    for m in FIRE.finditer(src):
        fired.setdefault(m.group(1).lower(), 0)
        fired[m.group(1).lower()] += 1

    # Only the names inside SV_IOOutputKnown count -- `lk == "..."` appears
    # nowhere else today, but scoping it means a future reader elsewhere in the
    # file cannot silently widen what this script thinks is registered.
    i = src.find("SV_IOOutputKnown")
    if i < 0:
        print("iocheck: SV_IOOutputKnown not found in %s" % path)
        return 2
    body = src[i:src.find("\n};", i)]
    known = set(KNOWN.findall(body))

    cry_wolf = sorted(set(fired) - known)
    lying = sorted(known - set(fired))

    if cry_wolf:
        print("FIRED BUT NOT REGISTERED -- these make the census cry wolf:")
        for n in cry_wolf:
            print("    %-22s (%d call site(s))" % (n, fired[n]))
    if lying:
        print("REGISTERED BUT NEVER FIRED -- these make silence read as "
              "'implemented', which is the worse direction:")
        for n in lying:
            print("    %s" % n)

    if not cry_wolf and not lying:
        print("iocheck: OK -- %d output name(s) across %d fire site(s), "
              "plus %d computed (%s)."
              % (len(fired), sum(fired.values()), len(KNOWN_DYNAMIC),
                 ", ".join(sorted(set(KNOWN_DYNAMIC.values())))))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
