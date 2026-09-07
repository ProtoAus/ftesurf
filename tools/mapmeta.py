#!/usr/bin/env python3
"""
mapmeta.py -- per-map tier, stage count, bonus count and thumbnail id, extracted
from Momentum Mod's own local cache with no engine and no network in the path.

WHY THIS EXISTS.  The map browser wants to say, on every row, what Momentum's own
UI says: a tier, whether the map is linear or staged, how many stages and bonuses
it has, and a picture.  None of that is in the BSP, and QC cannot inflate zlib, so
it has to be projected to a flat table ahead of time.  This is that step.

WHERE THE DATA IS.  Momentum caches its map database in

    momentum/_cache/approved_<n>.dat        1149 maps, status 0
    momentum/_cache/submission_<n>.dat      1023 maps, status 3 or 4

which are NOT a Valve format despite living next to some.  The container is

    magic       4 bytes   "MSML"
    rawsize     uint32    length of the decompressed payload
    count       uint32    number of records in it
    payload     zlib      a plain JSON array, one object per map

Verified byte-exact on this install: approved_1480.dat declares 12,395,228 bytes
and 1149 records, and `zlib.decompress(data[12:])` produces exactly that.

THE ONE TRAP, and it is easy to miss.  `leaderboards[]` is duplicated per STYLE and
per GAMEMODE.  surf_ace carries 210 leaderboard entries; count the `trackType == 1`
rows naively and you get 32 stages for a map that has 8.  The real shape is

    gamemode   1 = surf, 2 = bhop, then 3 and 5..13 for the other modes
    trackType  0 = main track, 1 = stage, 2 = bonus
    trackNum   1-based within the track type
    style      0 = normal, and see STYLE_MAIN below -- 8 and 9 are NOT joke styles
    tier       1..10, or null when the mode is unranked FOR THIS MAP
    linear     bool, on main tracks

so every count must be filtered to a MAIN style and to ONE gamemode.  Which one is
answered by the data itself: only the map's native mode carries a non-null `tier`.
surf_ace is tier 1 under gamemode 1 and null under all eleven others; bhop_eazy is
tier 1 under gamemode 2.  That is the selector used here, with a name-prefix guess
and then a popularity count as fallbacks for maps nobody has ranked.

THE SECOND TRAP, and it is the reason surf_tensor2 had no tier for three builds.
A map that is still IN SUBMISSION has no ranked tier yet, so every one of its
`leaderboards[]` rows carries `tier: null` -- and reading only that field silently
untiers the entire Unlisted and Beta sections.  Measured on this install: 1020 of
the 1023 submission records have no leaderboard tier at all, while all 1023 carry
suggestion tiers.

The tier for those lives in `submission.suggestions[]` instead, and Momentum's own
UI switches between the two in exactly one place --
`panorama/scripts/common/maps.ts:47-59`:

    export function getTier(staticData, gamemode, trackType = MAIN, trackNum = 1) {
        return MapStatuses.IN_SUBMISSION.includes(staticData.status)
            ? staticData.submission.suggestions.find(
                  (s) => s.gamemode === gamemode &&
                         s.trackType === trackType && s.trackNum === trackNum
              )?.tier
            : getTrack(staticData, gamemode, trackType, trackNum)?.tier;
    }

`IN_SUBMISSION` is PRIVATE_TESTING(1), PUBLIC_TESTING(3), CONTENT_APPROVAL(2) and
FINAL_APPROVAL(4) -- `map-status.enum.ts` calls 1 "available in the Beta tab to
users with an accepted MapTestingInvite" and 3 "available to all users in the Beta
tab".  That is a port with a citation, not a reconstruction, and it is why the
STATUS field is read at all.

THE THIRD TRAP, and this comment block is what caused it.  The line above used to
read "style 0 = normal; 1..9 are the joke/challenge styles", which is wrong, and
every filter in this file was written to trust it.  `style.enum.ts` says:

    0 NORMAL   1 BHOP_HALF_SIDEWAYS   2 SURF_HALF_SIDEWAYS   3 SIDEWAYS
    4 W_ONLY   5 AD_ONLY   6 S_ONLY   7 BACKWARDS   8 PRO   9 TELEPORT

**8 and 9 are the two canonical KZ run types** -- pro (no teleports) and TP -- not
jokes, and for a KZ map they are frequently the ONLY boards that carry a tier.
Measured here: 33 maps have no style-0 main-track tier but do have one under 8 and
9, all of them `kz_`, and the style-0 filter was throwing their tier, their stage
count and their bonus count away.  Five of them also read the wrong gamemode,
because `pick_gamemode` never saw those rows and fell through to the name prefix.

PRO and TELEPORT never disagree with each other on tier; the only disagreements are
between gamemode 5 (CLIMB_KZT) and 6 (CLIMB_16), on 4 maps, which the usual
most-common rule resolves.  See STYLE_MAIN.

A SUGGESTED TIER IS NOT A RANKED ONE.  It is what the submitter and the testers
think the map is worth, and it moves before approval.  Momentum keeps them in a
separate tab; we show one list, so the distinction has to survive into the row --
hence the `tsrc` column, which says where each tier came from.  Writing a
suggestion into the same column unmarked would have the browser assert something
the data does not.

LAYERING.  Momentum's cache first, its zone files second, a hand-edited override
file last:

  * The cache is authoritative for tier -- it is the only source that has one.
  * `maps/zones/{online,local}/<map>.json` (524 + 13 files) fills stages and
    bonuses for maps with no cache record.  This is the same file the running game
    parses (src/shared/sh_zones.qc), so where the two sources disagree the zone
    file is what the timer will actually do -- disagreements are counted and
    reported rather than silently resolved.
  * Installed BSPs that differ from a cache row only by a PORT SUFFIX inherit that
    row -- see alias_rows().  `surf_aircontrol_ksf` is `surf_aircontrol` as ported
    to a KSF server; Momentum has never had a record under the ported name.
  * `ftesurf/data/mapmeta_override.txt` wins over all of them.  It is how a CS:S-only
    map, which appears in no other source, gets a tier.  It is also the ONLY answer
    for a map that is in neither .dat and is nobody's port -- an unlisted map nobody
    on this machine has cached cannot be recovered offline at all.

HOW MUCH IS STILL MISSING, measured rather than assumed, because the number is not
what the tier work suggests.  Of 1163 BSPs actually installed on this machine
(cstrike 1084 + hl2 79), 427 had a tier before this pass and **726 had no row at
all**.  Those 726 are CS:S community maps Momentum has no record of; the alias pass
recovers 77 of them and nothing offline can recover the rest.  The 55 untiered rows
in mapmeta.txt are a different and much smaller population -- do not confuse the
two when reading --report.

An unknown field is written as "-", never as 0.  "tier 0" is a lie; "untiered" is
not, and the browser renders the two differently.

Usage:
    python mapmeta.py                       # write ftesurf/data/mapmeta.txt
    python mapmeta.py --report              # print coverage stats and write NOTHING
    python mapmeta.py --check surf_ace      # dump one map's raw leaderboards

`--report` DOES NOT WRITE, and that is deliberate: it used to fall through to
write(), so "just print the stats" silently regenerated the table -- and because
write() emits page/cell as "-" for mapthumbs.py to fill in afterwards, a bare run
of this tool would blank the thumbnail atlas coordinates for 2167 of 2194 rows.
write() now carries existing page/cell forward (see keep_atlas), so a regeneration
is safe on its own, but --report still refuses to write because a reporting flag
that mutates its input is a trap whatever it costs.
"""

import argparse
import glob
import json
import os
import struct
import sys
import zlib
from collections import Counter

# ---------------------------------------------------------------------------
#  Paths.  Absolute by default because both trees are fixed installs on this
#  machine; --momentum / --out override them for anyone else's.
# ---------------------------------------------------------------------------
MOMENTUM = r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum"
SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # C:\FTESurf
OUT = os.path.join(SURFDIR, "ftesurf", "data", "mapmeta.txt")
OVERRIDE = os.path.join(SURFDIR, "ftesurf", "data", "mapmeta_override.txt")

MSML_MAGIC = b"MSML"

# Where the installed maps are, for the alias pass.  Missing dirs are skipped, so
# this is safe on a machine with a different set of games mounted.  These mirror
# ftesurf/fs_addons.txt rather than being a second opinion about what is mounted.
MAPDIRS = (
    os.path.join(SURFDIR, "ftesurf", "maps"),
    r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source\cstrike\maps",
    r"C:\Program Files (x86)\Steam\steamapps\common\Half-Life 2\hl2\maps",
)

# Leaderboard styles, from panorama/scripts/common/web/enums/style.enum.ts.
#
# STYLE_MAIN is the search order for "the board that ranks this map", and the
# order matters: NORMAL first for every mode that has one, then PRO and TELEPORT,
# which are KZ's two canonical run types and are the only boards a KZ map is
# likely to carry.  See THE THIRD TRAP in the module docstring -- reading style 0
# alone silently untiered 33 maps and zeroed their stage and bonus counts.
ST_NORMAL = 0
ST_PRO = 8
ST_TELEPORT = 9
STYLE_MAIN = (ST_NORMAL, ST_PRO, ST_TELEPORT)

# gamemode ids, from the census across the whole library
GM_SURF = 1
GM_BHOP = 2

# Gamemode ids, from panorama/scripts/common/web/enums/gamemode.enum.ts.
#
# THIS TABLE WAS WRONG FOR EVERY ID FROM 3 UP, and had been since it was written.
# The old one was reconstructed by matching a population census to the modes we
# expected to be popular, which is a guess that produced a plausible-looking
# permutation: it read 7 as "ahop" (it is RJ), 8 as "parkour" (SJ), 9 as "conc"
# (AHOP), 12 as "kz" (DEFRAG_VQ3).  The names were only ever used for display and
# for the PREFIX_MODE fallback, so nothing crashed -- the map browser simply
# labelled a third of the library with the wrong gamemode and filtered on it.
#
# Confirmed against the data as well as the enum: of 251 `rj_`-prefixed maps with
# a ranked main-track tier, 251 are gamemode 7; 185 of 195 `sj_` are 8; 26 of 27
# `ahop_` are 9; 203 of 254 `kz_` are 5.  Both sources agree, so this is not a
# reading of one file.
#
# 4 (CLIMB_MOM) and 13 (DEFRAG_VTG) do not occur anywhere in this library.
MODE_NAMES = {
    1: "surf", 2: "bhop", 3: "bhop-hl1", 4: "climb", 5: "kz", 6: "climb-16",
    7: "rj", 8: "sj", 9: "ahop", 10: "conc",
    11: "df-cpm", 12: "df-vq3", 13: "df-vtg",
}

# panorama/scripts/common/web/enums/map-status.enum.ts, verbatim.
ST_APPROVED = 0
ST_PRIVATE_TESTING = 1          # "the Beta tab, to users with an accepted invite"
ST_CONTENT_APPROVAL = 2
ST_PUBLIC_TESTING = 3           # "the Beta tab, to all users"
ST_FINAL_APPROVAL = 4
ST_DISABLED = 5

# MapStatuses.IN_SUBMISSION, same file.  These are the maps whose tier lives in
# submission.suggestions rather than in leaderboards -- see the module docstring.
IN_SUBMISSION = frozenset((ST_PRIVATE_TESTING, ST_PUBLIC_TESTING,
                           ST_CONTENT_APPROVAL, ST_FINAL_APPROVAL))

# Where a tier came from.  Written as column 10 so the browser can render a
# suggestion differently from a ranked tier instead of asserting both equally.
TS_RANK = "rank"        # a main-style main-track leaderboard on an approved map
TS_SUGG = "sugg"        # submission.suggestions -- an estimate, not a ranking
TS_OVER = "over"        # data/mapmeta_override.txt said so
TS_ALIAS = "alias"      # inherited from the un-suffixed map -- see alias_rows()
TS_NONE = "-"

# Port and version suffixes an installed map can carry that the Momentum record
# does not.  A map is only aliased when the WHOLE name minus one or more of these
# matches an existing row, so the gamemode prefix has to survive intact.
#
# THAT RESTRICTION IS THE WHOLE SAFETY ARGUMENT.  Stripping the prefix as well --
# the obvious "normalise both sides" version -- matches 120 maps instead of 78,
# and the extra 42 include `bhop_seraph` -> `surf_seraph`, `surf_bob` -> `sj_bob`
# and `surf_compact` -> `conc_compact`, which are different maps that happen to
# share a stem.  Same prefix, same stem, suffix only.
ALIAS_SUFFIXES = (
    "mom", "go", "csgo", "css", "fix", "fixed", "final",
    "redux", "remake", "reloaded", "new", "old",
    "ksf",      # the KSF server's ports
    "njv",      # a mapper's ports
    "nyx", "hdr", "lite", "xl",
)

# Name prefix -> gamemode, used only when neither the leaderboards nor the
# suggestions carry a tier.  Every entry is the modal answer from the census
# above rather than an assumption, and the sample size is in the comment because
# a prefix that is genuinely mixed should not read as though it were certain.
#
# `trikz_` is gone: trikz is a surf STYLE, not a gamemode, and there is no id for
# it -- it used to map to 13, which is DEFRAG_VTG.  `climb_` points at CLIMB_KZT
# because CLIMB_MOM (4) has no maps at all.
PREFIX_MODE = {
    "surf_":  GM_SURF,      # 557/557
    "bhop_":  GM_BHOP,      # 493/501
    "rj_":    7,            # 251/251
    "sj_":    8,            # 185/195
    "kz_":    5,            # 203/254
    "bkz_":   5,            # 3/5
    "climb_": 5,            # no sample; CLIMB_MOM is empty in this library
    "df_":    11,           # 140/167
    "defrag_": 11,
    "conc_":  10,           # 61/124, tied with sj -- conc maps carry both boards
    "ahop_":  9,            # 26/27
}


class Meta:
    """One map's row.  `-` for anything genuinely unknown."""

    __slots__ = ("name", "tier", "linear", "stages", "bonuses",
                 "thumb", "mode", "page", "cell", "origin", "tsrc", "status")

    def __init__(self, name):
        self.name = name
        self.tier = None
        self.linear = None
        self.stages = None
        self.bonuses = None
        self.thumb = None
        self.mode = None
        self.page = None
        self.cell = None
        self.origin = ""      # which source(s) filled this in
        self.tsrc = TS_NONE   # where `tier` came from; column 10
        self.status = None    # MapStatus, for the report and the merge rule

    def field(self, v):
        if v is None:
            return "-"
        if isinstance(v, bool):
            return "1" if v else "0"
        return str(v)

    def line(self):
        # COLUMN 10 IS APPENDED, NEVER INSERTED.  m_main.qc reads argv(0..9) after
        # an `if (n < 10) continue` guard, so an old menu.dat reads a new file
        # correctly and simply does not see the provenance -- the same additive
        # rule the .rec header follows.
        return "meta %s %s %s %s %s %s %s %s %s %s" % (
            self.name,
            self.field(self.tier), self.field(self.linear),
            self.field(self.stages), self.field(self.bonuses),
            self.field(self.page), self.field(self.cell),
            self.field(self.thumb), self.field(self.mode),
            self.tsrc)


# ---------------------------------------------------------------------------
#  The MSML cache
# ---------------------------------------------------------------------------
def read_msml(path):
    """Return the decoded JSON array, or raise with a useful message."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != MSML_MAGIC:
        raise SystemExit("%s: not an MSML container (magic %r)" % (path, data[:4]))
    rawsize, count = struct.unpack_from("<II", data, 4)
    payload = zlib.decompress(data[12:])
    if len(payload) != rawsize:
        # Not fatal -- the header is a hint, the stream is the truth -- but it
        # means the format has moved and the rest of this file is now a guess.
        print("  ! %s: header says %d bytes, got %d"
              % (os.path.basename(path), rawsize, len(payload)), file=sys.stderr)
    maps = json.loads(payload)
    if len(maps) != count:
        print("  ! %s: header says %d records, got %d"
              % (os.path.basename(path), count, len(maps)), file=sys.stderr)
    return maps


def suggestions(m):
    """submission.suggestions[], or [] for an approved map."""
    return ((m.get("submission") or {}).get("suggestions")) or []


def main_rows(lbs, style, gm=None):
    """Main-track leaderboard rows for one style, optionally one gamemode."""
    return [l for l in lbs
            if l.get("style") == style and l.get("trackType") == 0
            and (gm is None or l.get("gamemode") == gm)]


def pick_gamemode(m, lbs, name):
    """The map's native gamemode.

    Only the mode a map is actually ranked in carries a non-null tier, so that is
    the signal -- and for a map in submission the rankings do not exist yet, so the
    SUGGESTIONS are asked the same question first.  Without that, every submission
    map falls through to the name prefix, and a `surf_`-prefixed map that is really
    ranked as something else reads the wrong row.

    Falls back to the name prefix, then to whichever mode has the most entries --
    both of which are guesses, and both of which now only matter for a map with no
    tier in any source.
    """
    # STYLE_MAIN in order, and the first style that ranks this map at all wins the
    # gamemode vote.  A KZ map ranked only under PRO and TELEPORT used to reach the
    # prefix fallback, which said 5 (CLIMB_KZT) for every `kz_` name -- wrong for
    # the five whose boards are actually gamemode 6 (CLIMB_16).
    for style in STYLE_MAIN:
        tiered = [l["gamemode"] for l in main_rows(lbs, style)
                  if l.get("tier") is not None]
        if tiered:
            return Counter(tiered).most_common(1)[0][0]

    sugg = [s["gamemode"] for s in suggestions(m)
            if s.get("trackType") == 0 and s.get("tier") is not None
            and s.get("gamemode") is not None]
    if sugg:
        return Counter(sugg).most_common(1)[0][0]

    low = name.lower()
    for pfx, gm in PREFIX_MODE.items():
        if low.startswith(pfx):
            return gm

    if lbs:
        return Counter(l["gamemode"] for l in lbs).most_common(1)[0][0]
    return None


def suggested_tier(m, gm, tracktype=0, tracknum=1):
    """maps.ts:getTier()'s submission branch, ported.

    Only consulted for a status in IN_SUBMISSION, because that is the condition
    Momentum's own UI switches on -- an approved map's suggestions are historical
    and its leaderboard is the ranking that replaced them.
    """
    if m.get("status") not in IN_SUBMISSION:
        return None
    for s in suggestions(m):
        if (s.get("gamemode") == gm and s.get("trackType") == tracktype
                and s.get("trackNum") == tracknum):
            return s.get("tier")
    return None


def from_cache(m):
    """Project one cache record to a Meta."""
    meta = Meta(m["name"])
    lbs = m.get("leaderboards") or []
    gm = pick_gamemode(m, lbs, m["name"])
    meta.mode = gm
    meta.status = m.get("status")

    # One gamemode, and the first style in STYLE_MAIN that actually ranks this map.
    # Falling straight to style 0 is what threw away 33 KZ maps -- see THE THIRD
    # TRAP.  `style` is carried out of the loop because the stage and bonus counts
    # have to be read from the SAME board as the tier: a KZ map's trackType 1/2
    # rows live under PRO and TELEPORT too, so counting them at style 0 returns 0.
    style = ST_NORMAL
    for s in STYLE_MAIN:
        main = main_rows(lbs, s, gm)
        if main and main[0].get("tier") is not None:
            style = s
            break
    else:
        main = main_rows(lbs, ST_NORMAL, gm)

    if main:
        meta.tier = main[0].get("tier")
        meta.linear = main[0].get("linear")
    if meta.tier is not None:
        meta.tsrc = TS_RANK
    else:
        # The Unlisted and Beta sections.  maps.ts:getTier(), and the reason a
        # status-3 map like surf_tensor2 read "-" until now.
        meta.tier = suggested_tier(m, gm)
        if meta.tier is not None:
            meta.tsrc = TS_SUGG

    # Counts come from the same (gamemode, style) pair the tier did.  For an
    # ordinary map that is style 0 and nothing changes: leaderboards carries
    # trackType 1/2 rows for a submission map even with every tier null, which is
    # why surf_tensor2 already read its 8 stages and 6 bonuses correctly.
    mine = [l for l in lbs if l.get("gamemode") == gm and l.get("style") == style]
    meta.stages = len([l for l in mine if l.get("trackType") == 1])
    meta.bonuses = len([l for l in mine if l.get("trackType") == 2])

    thumb = m.get("thumbnail") or {}
    meta.thumb = thumb.get("id")
    meta.origin = "cache"
    return meta


# ---------------------------------------------------------------------------
#  The zone files -- the second source, and the one the running game uses
# ---------------------------------------------------------------------------
def zone_counts(path):
    """(stages, bonuses) from a Momentum zone file, or None if unreadable.

    Schema is documented at src/shared/sh_zones.qc:26-38 and matches what the mod
    parses at runtime: tracks.main.zones.segments[] is the stage list (one segment
    means linear) and tracks.bonuses[] is the bonus list.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            j = json.load(f)
    except (OSError, ValueError):
        return None
    tracks = j.get("tracks") or {}
    main = tracks.get("main") or {}
    segs = ((main.get("zones") or {}).get("segments")) or []
    bonuses = tracks.get("bonuses") or []
    # A linear map is one segment here but zero stage leaderboards in the cache;
    # normalise to the cache's convention so the two are comparable.
    stages = 0 if len(segs) <= 1 else len(segs)
    return stages, len(bonuses)


def scan_zones(momentum):
    """map name (lowercased) -> (stages, bonuses, which dir it came from)."""
    out = {}
    # local wins over online, matching the mod's own lookup order
    # (src/server/sv_zones.qc:121-126).
    for sub in ("online", "local"):
        d = os.path.join(momentum, "maps", "zones", sub)
        for p in glob.glob(os.path.join(d, "*.json")):
            counts = zone_counts(p)
            if counts is None:
                continue
            nm = os.path.splitext(os.path.basename(p))[0]
            out[nm.lower()] = (counts[0], counts[1], sub)
    return out


# ---------------------------------------------------------------------------
#  Ports -- installed maps that ARE a map Momentum knows, under another name
# ---------------------------------------------------------------------------
def installed_maps(dirs=MAPDIRS):
    """Lowercased basenames of every installed .bsp.  Missing dirs are skipped."""
    out = set()
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for p in glob.glob(os.path.join(d, "*.bsp")):
            out.add(os.path.splitext(os.path.basename(p))[0].lower())
    return out


def strip_suffix(name):
    """`surf_aircontrol_ksf` -> `surf_aircontrol`; unchanged if nothing stripped.

    Repeated, because ports stack: `surf_x_ksf_fix` is two suffixes deep.  A bare
    `_v2`/`_b3`/`_r2` counts as one, spelled numerically rather than listed.
    """
    while True:
        cut = name.rsplit("_", 1)
        if len(cut) != 2 or not cut[0]:
            return name
        head, tail = cut
        if tail in ALIAS_SUFFIXES:
            name = head
            continue
        # _v2 / _b3 / _r2 and friends: one letter then digits, nothing else.
        if (len(tail) > 1 and tail[0] in "vbr" and tail[1:].isdigit()):
            name = head
            continue
        return name


def alias_rows(metas, stats, report=False):
    """Give an installed port the row of the map it is a port OF.

    Momentum has no record of `surf_aircontrol_ksf`; it has `surf_aircontrol`, and
    they are the same map with a server's fixes on top.  The row is copied, the
    name is the installed one, and the tier is marked TS_ALIAS so the browser can
    say "probably this" rather than asserting a ranking -- exactly the argument
    that gave suggested tiers their own marking.

    Only maps that are actually INSTALLED get a row: an alias for a map you do not
    have is a browser entry you cannot click.  The thumbnail is inherited too but
    page/cell are not, because those are atlas coordinates for a specific image
    and mapthumbs.py assigns them.
    """
    made = []
    for nm in sorted(installed_maps()):
        if nm in metas:
            continue
        base = strip_suffix(nm)
        if base == nm or base not in metas:
            continue

        src = metas[base]
        meta = Meta(nm)
        meta.tier, meta.linear = src.tier, src.linear
        meta.stages, meta.bonuses = src.stages, src.bonuses
        meta.thumb, meta.mode, meta.status = src.thumb, src.mode, src.status
        meta.origin = "alias/" + src.name
        meta.tsrc = TS_ALIAS if src.tier is not None else TS_NONE
        metas[nm] = meta
        stats["alias"] += 1
        made.append((nm, src.name, src.tier))

    if report and made:
        tiered = sum(1 for _, _, t in made if t is not None)
        print("\n  %d installed maps aliased to an un-suffixed Momentum row "
              "(%d with a tier).  First 10:" % (len(made), tiered))
        for nm, base, t in made[:10]:
            print("    %-34s -> %-28s T%s" % (nm, base, t))
    return made


# ---------------------------------------------------------------------------
#  The override file
# ---------------------------------------------------------------------------
def read_override(path):
    """Same line format this tool emits, so a row can be copied out and edited.

    Only the fields present are applied; `-` means "leave whatever the other
    sources found", which is different from "unknown".  That lets an override set
    just a tier without having to restate the stage counts.
    """
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            t = s.split()
            if t[0] != "meta" or len(t) < 2:
                print("  ! %s:%d: not a meta line, ignored" % (path, ln), file=sys.stderr)
                continue
            out[t[1].lower()] = t
    return out


def apply_override(meta, t):
    def g(i, cast):
        if len(t) <= i or t[i] == "-":
            return None
        try:
            return cast(t[i])
        except ValueError:
            return None

    for idx, attr, cast in ((2, "tier", int), (3, "linear", lambda v: bool(int(v))),
                            (4, "stages", int), (5, "bonuses", int),
                            (8, "thumb", str), (9, "mode", int)):
        v = g(idx, cast)
        if v is not None:
            setattr(meta, attr, v)
            if attr == "tier":
                meta.tsrc = TS_OVER
    meta.origin += "+override"


# ---------------------------------------------------------------------------
def build(momentum, override_path, report=False):
    metas = {}          # lowercased name -> Meta
    stats = Counter()

    dats = sorted(glob.glob(os.path.join(momentum, "_cache", "*.dat")))
    if not dats:
        print("no _cache/*.dat found under %s" % momentum, file=sys.stderr)
    for p in dats:
        try:
            records = read_msml(p)
        except SystemExit:
            raise
        except Exception as e:                                  # noqa: BLE001
            print("  ! %s: %s" % (os.path.basename(p), e), file=sys.stderr)
            continue
        print("  %-24s %5d maps" % (os.path.basename(p), len(records)))
        for m in records:
            nm = m.get("name")
            if not nm:
                continue
            key = nm.lower()
            meta = from_cache(m)

            # A NAME IN BOTH FILES KEEPS THE RANKED ROW, and this rule had to be
            # rewritten rather than kept.  It used to read "keep whichever row has
            # a tier at all", which worked only because a submission row never had
            # one.  Now that it does, that test would let a suggestion overwrite
            # the ranking the approved cache already holds -- a map that got
            # approved and then resubmitted for a new version would silently lose
            # its real tier to an estimate.  So the comparison is on the SOURCE.
            if key in metas and metas[key].tsrc == TS_RANK and meta.tsrc != TS_RANK:
                continue

            metas[key] = meta
            stats["cache"] += 1

    zones = scan_zones(momentum)
    print("  %-24s %5d maps" % ("maps/zones/*", len(zones)))

    disagree = []
    for key, (st, bn, sub) in zones.items():
        meta = metas.get(key)
        if meta is None:
            meta = Meta(key)
            meta.stages, meta.bonuses = st, bn
            meta.linear = (st == 0)
            meta.origin = "zones/" + sub
            metas[key] = meta
            stats["zone-only"] += 1
            continue
        if meta.stages is None:
            meta.stages, meta.bonuses = st, bn
            meta.origin += "+zones"
            stats["zone-filled"] += 1
        elif (meta.stages, meta.bonuses) != (st, bn):
            disagree.append((meta.name, meta.stages, meta.bonuses, st, bn))

    # After the zone pass so a port with its own zone file keeps that, and before
    # the override pass so a hand-written row still wins.
    alias_rows(metas, stats, report=report)

    overrides = read_override(override_path)
    for key, t in overrides.items():
        meta = metas.get(key)
        if meta is None:
            meta = Meta(t[1])
            meta.origin = "override"
            metas[key] = meta
            stats["override-only"] += 1
        apply_override(meta, t)
        stats["override"] += 1

    if disagree:
        print("\n  %d maps where the cache and the zone file disagree on counts."
              % len(disagree))
        print("  The cache value is kept (it is what Momentum's UI shows); the zone "
              "file is\n  what this game's timer will actually run.  First 10:")
        for nm, cs, cb, zs, zb in disagree[:10]:
            print("    %-34s cache %d st %d b   zones %d st %d b" % (nm, cs, cb, zs, zb))

    if report:
        tiered = sum(1 for m in metas.values() if m.tier is not None)
        thumbed = sum(1 for m in metas.values() if m.thumb)
        linear = sum(1 for m in metas.values() if m.linear)
        print("\n  %d maps total, %d tiered, %d with a thumbnail id, %d linear"
              % (len(metas), tiered, thumbed, linear))
        print("  sources: %s" % dict(stats))

        # Broken out because the two are not the same claim: a ranked tier is what
        # Momentum's leaderboard says, a suggested one is what the submitter and
        # the testers think, and the browser renders them differently.
        tsrc = Counter(m.tsrc for m in metas.values())
        print("  tiers:   %s" % dict(tsrc.most_common()))

        modes = Counter(MODE_NAMES.get(m.mode, str(m.mode)) for m in metas.values())
        print("  modes:   %s" % dict(modes.most_common()))

        # THE NUMBER THAT ACTUALLY MATTERS, and it is not the one above.  The
        # browser shows maps you can load, so coverage is measured against the
        # installed BSPs -- a table full of rows for maps that are not on disk
        # reads as good coverage and is not.
        inst = installed_maps()
        if inst:
            have = inst & set(metas)
            tier_i = sum(1 for n in have if metas[n].tier is not None)
            print("\n  installed BSPs: %d.  %d have a tier, %d have a row but no "
                  "tier, %d have no row at all."
                  % (len(inst), tier_i, len(have) - tier_i, len(inst) - len(have)))
            print("  The last group is CS:S community maps Momentum has no record "
                  "of.  Only\n  data/mapmeta_override.txt can reach them, and it "
                  "needs a source this tool\n  does not have offline.")

    return metas


def keep_atlas(metas, out):
    """Carry page/cell forward from the file we are about to overwrite.

    mapthumbs.py fills those two columns in AFTER this tool runs, and this tool
    has no idea what an atlas cell is -- so writing them as "-" (which is what
    Meta starts with) meant that regenerating the table blanked the thumbnail
    coordinates for 2167 of 2194 rows and every picture in the browser vanished
    until mapthumbs.py was run again.  Nothing said so; the tier columns all
    looked fine.

    Reading them back makes a bare `python mapmeta.py` idempotent with respect to
    the atlas.  A row whose thumbnail UUID has CHANGED does not keep its old
    coordinates -- they point at the previous image.
    """
    if not os.path.exists(out):
        return 0
    kept = 0
    with open(out, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            t = raw.split()
            if len(t) < 10 or t[0] != "meta":
                continue
            meta = metas.get(t[1].lower())
            if meta is None or meta.page is not None:
                continue
            if t[6] == "-" or t[7] == "-" or t[8] != str(meta.thumb):
                continue
            try:
                meta.page, meta.cell = int(t[6]), int(t[7])
            except ValueError:
                continue
            kept += 1
    return kept


def write(metas, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    kept = keep_atlas(metas, out)
    if kept:
        print("  kept %d atlas page/cell pair(s) from the previous table" % kept)
    rows = sorted(metas.values(), key=lambda m: m.name.lower())
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("FTESURF-MAPMETA 1\n")
        f.write("# written by tools/mapmeta.py -- do not edit, use "
                "data/mapmeta_override.txt\n")
        f.write("# meta <name> <tier> <linear> <stages> <bonuses> <page> <cell> "
                "<thumbuuid> <mode> <tsrc>\n")
        f.write("# '-' means unknown, and is not the same as 0.  page/cell are "
                "filled in by mapthumbs.py.\n")
        f.write("# tsrc: rank = a ranked leaderboard tier; sugg = a SUBMITTER'S "
                "SUGGESTION, from a map\n")
        f.write("#       still in the Unlisted/Beta sections, and an estimate "
                "rather than a ranking;\n")
        f.write("#       alias = inherited from the same map without its port "
                "suffix (surf_x_ksf\n")
        f.write("#       from surf_x); over = mapmeta_override.txt.  "
                "See maps.ts:getTier().\n")
        for m in rows:
            f.write(m.line() + "\n")
    return len(rows)


def check_one(momentum, name):
    """Dump one map's raw leaderboards -- the debugging path for a wrong row."""
    for p in sorted(glob.glob(os.path.join(momentum, "_cache", "*.dat"))):
        for m in read_msml(p):
            if m.get("name", "").lower() != name.lower():
                continue
            st = m.get("status")
            print("%s  (%s, id %s, status %s%s)"
                  % (m["name"], os.path.basename(p), m.get("id"), st,
                     " IN_SUBMISSION" if st in IN_SUBMISSION else ""))
            print("thumbnail id: %s" % (m.get("thumbnail") or {}).get("id"))
            lbs = m.get("leaderboards") or []
            gm = pick_gamemode(m, lbs, m["name"])
            print("picked gamemode %s (%s)" % (gm, MODE_NAMES.get(gm, "?")))

            # Every main style, not just the one that won, because "which board
            # is this map actually ranked on" is the question that untiered 33
            # KZ maps -- and a row that reads wrong is usually a style question.
            for s in STYLE_MAIN:
                rows = [l for l in lbs
                        if l.get("gamemode") == gm and l.get("style") == s]
                if not rows:
                    continue
                print("style %d leaderboard rows for that mode:" % s)
                for l in rows:
                    print("   trackType %d trackNum %-3d tier %-5s linear %s"
                          % (l["trackType"], l["trackNum"],
                             l.get("tier"), l.get("linear")))

            # The other half of getTier(), printed whether or not it was used --
            # a map whose leaderboard tier and suggestion disagree is exactly the
            # case this command exists to make visible.
            sugg = suggestions(m)
            if sugg:
                print("submission.suggestions for that mode:")
                for s in sugg:
                    if s.get("gamemode") == gm:
                        print("   trackType %s trackNum %-3s tier %-5s type %s"
                              % (s.get("trackType"), s.get("trackNum"),
                                 s.get("tier"), s.get("type")))
            else:
                print("submission.suggestions: none (approved map)")

            print("-> %s" % from_cache(m).line())
            return
    print("%s: not in any _cache/*.dat" % name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--momentum", default=MOMENTUM, help="Momentum Mod game dir")
    ap.add_argument("--out", default=OUT, help="output mapmeta.txt")
    ap.add_argument("--override", default=OVERRIDE, help="hand-edited override table")
    ap.add_argument("--report", action="store_true",
                    help="print coverage stats and write nothing")
    ap.add_argument("--check", metavar="MAP", help="dump one map's raw leaderboards")
    a = ap.parse_args()

    if not os.path.isdir(a.momentum):
        raise SystemExit("Momentum dir not found: %s" % a.momentum)

    if a.check:
        check_one(a.momentum, a.check)
        return

    print("reading %s" % a.momentum)
    metas = build(a.momentum, a.override, report=a.report)

    # --report is READ-ONLY.  It used to fall through to write(), so asking for
    # the stats rewrote the table as a side effect -- see the module docstring.
    if a.report:
        print("\n--report: nothing written.  Run without it to write %s" % a.out)
        return

    n = write(metas, a.out)
    print("\nwrote %s  (%d maps)" % (a.out, n))


if __name__ == "__main__":
    main()
