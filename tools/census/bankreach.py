"""Census for P1079's reach: can one player's earlier attempt own a body write that lands later?

Usage: python tools/census/bankreach.py <maps dir> [out.json]
(the full library is the Pi's game/momentum/maps; count what it reads, do not quote a number).

Bank-counted writes are the SV_BankAffect callers in sv_entities.qc: AddOutput origin/
basevelocity/gravity, ModifySpeed, AddSpeed/AddHorizontalSpeed/AddVerticalSpeed, and
point_teleport Teleport/TeleportToCurrentPos/TeleportEntity. Targets resolve by targetname
only (SV_FindByName), so a write aimed at a name nothing carries lands nowhere.

(A) logic_timer whose OnTimer* chain SYNCHRONOUSLY reaches such a write -- through relay/
    case/branch/compare/counter/button-press/FireTimer only. Enabling a trigger is not
    followed: its later outputs run in the toucher's own fresh context. Split by whether
    player-activated I/O can Enable/Toggle/ResetTimer/FireTimer/RefireTime it; a timer only
    the world starts is attempt 0, which SV_BankAffect skips.
(B) body writes addressed to a name map I/O gives to players (AddOutput targetname on
    !activator/!player). The `naming`/`named_writes` totals show both halves can fire.
Static I/O graph only: no VScript, filters or point_servercommand.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib  # noqa: E402

ESC = "\x1b"
PLAYER_SRC = ("trigger_", "func_button", "func_rot_button", "momentary_rot_button", "func_door",
              "func_physbox", "func_breakable", "prop_")
TIMER_IN = {"enable", "toggle", "resettimer", "firetimer", "refiretime"}
SPEED_IN = {"modifyspeed", "addspeed", "addhorizontalspeed", "addverticalspeed"}
TELE_IN = {"teleport", "teleporttocurrentpos", "teleportentity"}
BODY_KEYS = ("origin", "basevelocity", "gravity")
SYNC = {"logic_relay": {"trigger"}, "logic_case": {"pickrandom", "pickrandomshuffle", "invalue"},
        "math_counter": {"add", "subtract", "setvalue", "multiply", "divide"},
        "logic_branch": {"test", "setvalue", "setvaluetest", "toggle", "toggletest"},
        "logic_compare": {"compare", "setvalue", "setvaluecompare"},
        "func_button": {"press"}, "logic_timer": {"firetimer"}}


def parse(path):
    pairs, _ = bsplib.read_pairs(path)
    if pairs is None:
        return None
    ents = []
    for ent in pairs:
        cn = tn = ""
        outs = []
        for k, v in ent:
            if k == "classname":
                cn = v.lower()
            elif k == "targetname":
                tn = v.lower()
        for k, v in ent:
            if not k.startswith("on"):
                continue
            parts = v.split(ESC if ESC in v else ",")
            if len(parts) < 2:
                continue
            outs.append((k, parts[0].strip().lower(), parts[1].strip().lower(),
                         parts[2].strip() if len(parts) > 2 else ""))
        ents.append({"cn": cn, "tn": tn, "outs": outs})
    return ents


def targets(byname, name):
    if not name or name.startswith("!"):
        return []
    if name.endswith("*"):
        return [i for n, ix in byname.items() if n.startswith(name[:-1]) for i in ix]
    return byname.get(name, [])


def addoutput_key(param):
    return param.split(" ", 1)[0].split(":", 1)[0].strip().lower()


def body_write(ents, byname, out, named=()):
    """Does this output write a bank-counted body it can actually reach?"""
    _, tgt, inp, param = out
    hit = tgt in ("!activator", "!player") or tgt in named or bool(targets(byname, tgt))
    if inp == "addoutput":
        return addoutput_key(param) in BODY_KEYS and hit
    if inp in SPEED_IN:
        return hit
    if inp in TELE_IN and not tgt.startswith("!"):
        return any(ents[i]["cn"] == "point_teleport" for i in targets(byname, tgt))
    return False


def sync_writes(ents, byname, outs, named, depth=4, path=()):
    hits = []
    for o in outs:
        if body_write(ents, byname, o, named):
            hits.append(" > ".join(path + ("%s.%s(%s)" % (o[1], o[2], o[3][:28]),)))
        elif depth > 0:
            for i in targets(byname, o[1]):
                if o[2] in SYNC.get(ents[i]["cn"], ()):
                    hits += sync_writes(ents, byname, ents[i]["outs"], named, depth - 1,
                                        path + ("%s.%s" % (o[1], o[2]),))
    return hits


def census(path):
    ents = parse(path)
    if ents is None:
        return None
    byname = collections.defaultdict(list)
    for i, e in enumerate(ents):
        if e["tn"]:
            byname[e["tn"]].append(i)
    named = set()
    for e in ents:
        for o in e["outs"]:
            if o[2] == "addoutput" and o[1] in ("!activator", "!player") and \
               addoutput_key(o[3]) == "targetname":
                bits = o[3].replace(":", " ").split()
                if len(bits) > 1:
                    named.add(bits[1].lower())
    driven = {i for i, e in enumerate(ents) if e["cn"].startswith(PLAYER_SRC)}
    frontier = set(driven)
    for _ in range(5):
        frontier = {j for i in frontier for o in ents[i]["outs"] for j in targets(byname, o[1])} - driven
        driven |= frontier
    timers = []
    for i, e in enumerate(ents):
        if e["cn"] != "logic_timer":
            continue
        hits = sync_writes(ents, byname, [o for o in e["outs"] if o[0].startswith("ontimer")],
                           named, path=(e["tn"] or "#%d" % i,))
        if hits:
            player = any(o[2] in TIMER_IN and i in targets(byname, o[1])
                         for s in driven for o in ents[s]["outs"])
            timers.append({"timer": e["tn"], "player_driven": player, "writes": hits[:3]})
    named_writes = [o for e in ents for o in e["outs"]
                    if o[2] == "addoutput" and addoutput_key(o[3]) in BODY_KEYS
                    and not o[1].startswith("!")]
    b = ["%s.%s(%s)" % (o[1], o[2], o[3][:28]) for e in ents for o in e["outs"]
         if o[1] in named and body_write(ents, byname, o, named)]
    return {"timers": timers, "player_named": b, "naming": bool(named),
            "named_writes": bool(named_writes)}


def main():
    root = sys.argv[1]
    maps = sorted(f for f in os.listdir(root) if f.lower().endswith(".bsp"))
    res, unread = {}, []
    for f in maps:
        try:
            r = census(os.path.join(root, f))
        except Exception as ex:  # a map that cannot be read is counted, not hidden
            unread.append("%s: %s" % (f, type(ex).__name__))
            continue
        if r is None:
            unread.append(f + ": no lumps")
            continue
        res[f[:-4]] = r
    a = [(m, t) for m, r in res.items() for t in r["timers"]]
    print("maps listed %d, read %d, unread %d" % (len(maps), len(res), len(unread)))
    print("maps naming players %d; maps with named-target body AddOutputs %d"
          % (sum(r["naming"] for r in res.values()), sum(r["named_writes"] for r in res.values())))
    print("A timers synchronously writing a reachable body: %d (player-drivable %d)"
          % (len(a), sum(t["player_driven"] for _, t in a)))
    for m, t in sorted(a, key=lambda x: x[0]):
        print("  A %-28s %-20s %s  %s" % (m, t["timer"], "PLAYER" if t["player_driven"] else "world",
                                          t["writes"][0]))
    bm = {m: r["player_named"] for m, r in res.items() if r["player_named"]}
    print("B body writes to a player-given name: %d maps" % len(bm))
    for m in sorted(bm):
        print("  B %-28s %s" % (m, "; ".join(bm[m][:3])))
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as fh:
            json.dump({"read": len(res), "unread": unread, "timers": a, "player_named": bm}, fh, indent=1)


if __name__ == "__main__":
    main()
