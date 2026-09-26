"""Togglable SOLID_BSP brushes whose box reaches a START zone.

Patch 443 round 5, lens B's fail-open.  SL_RowGrounded traces the world as it is
at LOAD time; the save records nothing about the world at WRITE time (see the save
grammar over SV_SaveWriteState -- 37 keys plus the magic since Patch 445 added
`hopped`; cfg/test/p443air.txt is a PRE-445 example of one, 36 lines).  The essay
covers the EMBEDDED twin --
at rest inside a disabled brush, the Enable fires, the load refuses it -- but the
version one unit HIGHER grants instead:

    hover just above where a StartDisabled brush's top face will be, inside a
    start slab, save at the apex tick (all three components under SL_ARM_SPEED 1),
    let the map's own button or logic_timer fire the Enable, then load.  The probe
    now finds nz 1.000 at frac ~0, returns TRUE, and SV_TimerArm launders the
    attempt's TF_SEGMENT|TF_PRACTICE.

Every flip resets at map load from StartDisabled (sv_entities.qc SV_IOEnable's
caller), and the save file outlives the map load -- which is what makes the two
sides differ with no cheat and no tainted ruleset.

THE QUESTION THIS ANSWERS: does any shipped map actually carry such a brush?
Severity was "not established" when the lens reported it, and an unmeasured
bypass is the thing this repo does not ship.

READ tools/census/README.md's grading section before quoting any number here.  An
entity box from the models lump is WHERE A BRUSH CAN BE, NOT WHERE IT IS, and that
has been wrong by a wide margin three times.  So this prints all three grades and
only CONTAINED survives the AABB problem.  None of them proves the top face is
reachable, or that the Enable is reachable without the map's cooperation -- a hit
here is a candidate for a live check, not a finding.

RESULT 2026-09-26, 1316 BSPs, 0 unreadable, 535 zoned, 0 without a start:

    NO SHIPPED MAP CARRIES ONE.  Grade 3 (contained) is ZERO.  Grade 2 has a
    single row and it is the AABB trap in person: surf_hourglass's `func_brush`
    `dynamic_flatsky`, StartDisabled 1, whose box is
    (-16128,-16128,-1536)..(16256,16128,9472) -- 32384 x 32256 x 11008, i.e. the
    whole map.  It is a skybox shell, so its AABB contains the start zone at
    z 800..1200 by construction while its faces are ~16000 u away.  There is no
    surface at the start to stand on.

    THE ENABLED-BY-IO PATH IS A REAL ZERO, NOT A DEAD BRANCH -- the self-check
    the run prints exists because this file would otherwise be a filter that
    never fired: 184 maps carry an Enable/Disable/Toggle output and 88 brush
    entities are named by one, and none of those 88 reaches a start zone.

So the fail-open is sound in MECHANISM and has no instance to exploit today.  It
stays a BACKLOG entry rather than a patch because nothing stops a future map from
adding one, and because the same hole is reachable by hand with no map at all:
`state.txt` is plain text in the player's own data/saves tree, and the save is
keyed by map NAME only -- the `map` key is written (SV_SaveWriteState) and NEITHER
READER EVER LOOKS AT IT, so a different .bsp under the same name is not noticed.
`infokey(world, "*mapcrc")` already exists in this tree, with the third verdict
done right, at SV_MapForeign in src/server/sv_timer.qc.
"""
import json, os, sys
import bsplib

MOM = os.environ.get("MOMENTUM_DIR",
                    r"C:\Program Files (x86)\Steam\steamapps\common\Momentum Mod Playtest\momentum")
MAPS = os.path.join(MOM, "maps")
ZON = os.path.join(MAPS, "zones", "online")

# SV_SpawnDoor / SV_SpawnPassableBrush / the SOLID_BSP catch-all.  A brush entity
# is SOLID_BSP unless its own spawnflag says otherwise, so the interesting set is
# "brush entity that is not a trigger", which `model *N` plus this exclusion gives.
TRIGGERISH = ("trigger_",)
NEVER_SOLID = ("func_illusionary", "func_dustcloud", "func_smokevolume",
               "func_precipitation", "env_", "info_", "light", "shadow_control",
               "sky_camera", "water_lod_control", "func_instance")


def json_starts(path):
    """-> list of (mins, maxs) boxes for every START zone in the file.

    Same reader as pushcensus.py: segments[0].checkpoints[0], which is the
    shipped zone JSON's spelling of a start.
    """
    d = json.load(open(path, 'r', encoding='utf-8-sig'))
    tracks = d.get('tracks') or {}
    out, cands = [], []
    if isinstance(tracks.get('main'), dict):
        cands.append(tracks['main'])
    for b in (tracks.get('bonuses') or []):
        if isinstance(b, dict):
            cands.append(b)
    for t in cands:
        segs = ((t.get('zones') or {}).get('segments') or [])
        if not segs:
            continue
        cps = (segs[0] or {}).get('checkpoints') or []
        if not cps:
            continue
        for r in (cps[0] or {}).get('regions') or []:
            pts = r.get('points') or []
            if len(pts) < 3:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            b = r.get('bottom', 0.0)
            h = r.get('height', 0.0)
            out.append(((min(xs), min(ys), b), (max(xs), max(ys), b + h)))
    return out


def ent_box(e, models):
    md = e.get('model', '')
    if not md.startswith('*'):
        return None
    try:
        o = [float(t) for t in e.get('origin', '0 0 0').split()[:3]]
    except ValueError:
        o = [0.0, 0.0, 0.0]
    if len(o) != 3:
        o = [0.0, 0.0, 0.0]
    try:
        i = int(md[1:])
    except ValueError:
        return None
    if i >= len(models):
        return None
    mn, mx, _ = models[i]
    return ((o[0] + mn[0], o[1] + mn[1], o[2] + mn[2]),
            (o[0] + mx[0], o[1] + mx[1], o[2] + mx[2]))


def gap(a, b):
    """0 if the AABBs intersect, else the largest per-axis separation."""
    g = 0.0
    for i in range(3):
        d = max(a[0][i] - b[1][i], b[0][i] - a[1][i])
        if d > g:
            g = d
    return g


def overlap_vol(a, b):
    v = 1.0
    for i in range(3):
        lo = max(a[0][i], b[0][i])
        hi = min(a[1][i], b[1][i])
        if hi <= lo:
            return 0.0
        v *= (hi - lo)
    return v


def contained(a, b):
    """a's whole box lies inside b."""
    return all(a[0][i] >= b[0][i] and a[1][i] <= b[1][i] for i in range(3))


def truthy(v):
    return str(v).strip() not in ("", "0", "false", "False")


def enable_targets(ents):
    """Names any entity output aims an Enable/Disable at.

    Source entity I/O is `target,Input,param,delay,times` in the VALUE of an
    On* key, so this is a substring test on values rather than a key whitelist --
    the key names are per-class (OnTrigger, OnPressed, OnTimer, OnMapSpawn...).
    """
    out = set()
    for e in ents:
        for k, v in e.items():
            if not isinstance(v, str) or ',' not in v:
                continue
            parts = v.split(',')
            if len(parts) < 2:
                continue
            inp = parts[1].strip().lower()
            if inp in ("enable", "disable", "toggle"):
                nm = parts[0].strip().lower()
                if nm:
                    out.add(nm)
    return out


def main():
    zfiles = {os.path.splitext(f)[0].lower(): os.path.join(ZON, f)
              for f in os.listdir(ZON) if f.lower().endswith('.json')}
    bsps = {os.path.splitext(f)[0].lower(): os.path.join(MAPS, f)
            for f in os.listdir(MAPS) if f.lower().endswith('.bsp')}

    st = dict(bsp_total=len(bsps), scanned=0, unreadable=0, zoned=0,
              nostart=0, cand_maps=0, sd_maps=0, io_maps=0,
              io_any_maps=0, io_any_ents=0)
    touch, over, cont = [], [], []

    for name in sorted(bsps):
        try:
            ents, models = bsplib.read(bsps[name])
        except Exception:
            st['unreadable'] += 1
            continue
        if ents is None:
            st['unreadable'] += 1
            continue
        st['scanned'] += 1

        if name not in zfiles:
            continue
        st['zoned'] += 1
        try:
            starts = json_starts(zfiles[name])
        except Exception:
            starts = []
        if not starts:
            st['nostart'] += 1
            continue

        io = enable_targets(ents)
        if io:
            st['io_any_maps'] += 1
        hit_sd = hit_io = False
        for e in ents:
            cn = (e.get('classname') or '').lower()
            if not cn or cn.startswith(TRIGGERISH) or cn.startswith(NEVER_SOLID):
                continue
            box = ent_box(e, models)
            if not box:
                continue
            nm = (e.get('targetname') or '').strip().lower()
            sd = truthy(e.get('StartDisabled', e.get('startdisabled', '0')))
            tog = nm in io if nm else False
            if tog:
                st['io_any_ents'] += 1
            if not (sd or tog):
                continue
            for s in starts:
                g = gap(box, s)
                if g > 0:
                    continue
                row = (name, cn, nm or '-', 'StartDisabled' if sd else 'IO',
                       round(overlap_vol(box, s), 1), contained(box, s))
                touch.append(row)
                if row[4] > 0:
                    over.append(row)
                if row[5]:
                    cont.append(row)
                if sd:
                    hit_sd = True
                else:
                    hit_io = True
                break
        if hit_sd or hit_io:
            st['cand_maps'] += 1
        if hit_sd:
            st['sd_maps'] += 1
        if hit_io:
            st['io_maps'] += 1

    print("bsp %(bsp_total)d  scanned %(scanned)d  unreadable %(unreadable)d  "
          "zoned %(zoned)d  no start %(nostart)d" % st)
    print("maps with a togglable solid touching a start: %(cand_maps)d  "
          "(StartDisabled %(sd_maps)d, enabled-by-IO %(io_maps)d)" % st)
    print()
    print("grade 1  touching (gap == 0), incl. zero-width: %d rows" % len(touch))
    print("grade 2  positive overlap volume:               %d rows" % len(over))
    print("grade 3  CONTAINED in the start zone:           %d rows  <- the only"
          % len(cont))
    print("         one that survives the AABB problem")
    print()
    print("SELF-CHECK -- a filter that never fires proves nothing:")
    print("  maps with any Enable/Disable/Toggle output: %d" % st['io_any_maps'])
    print("  brush entities named by one:                %d" % st['io_any_ents'])
    print("  ...of those, inside a start zone:            %d" % st['io_maps'])
    print()
    for lbl, rows in (("CONTAINED", cont), ("OVERLAP", over)):
        if not rows:
            continue
        print("--- %s ---" % lbl)
        for r in sorted(rows, key=lambda x: -x[4])[:40]:
            print("  %-28s %-22s %-18s %-13s vol %12.1f %s"
                  % (r[0], r[1], r[2][:18], r[3], r[4], "CONTAINED" if r[5] else ""))
        print()


if __name__ == "__main__":
    main()
