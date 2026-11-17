"""New maps within half an hour, beside mapwatch (P1601).

  python3 mapnew.py [--go] [--site-zones DIR]      (cron, every 30 minutes)

Lex, 17 Nov 2026: new Momentum and KSF maps every 30 minutes.  mapwatch's
back-off IS its 6-hourly cadence (strikes, shelving, purges), so it stays at
that.  This route takes only a name the library does not hold, from the head
of each list:
  Momentum  /v1/maps?gamemode=1|2|3&take=MOM_HEAD -- newest id first, without
            leaderboards (a page of 100: 1.7 MB with, 0.3 MB without); a new
            map's tier comes from its own reply.  A map approved long after its
            submission can sit past the head (4 of the 80 surf/bhop maps
            approved in the 90 days to 17 Nov); mapwatch's full read takes it.
  KSF       /api/maps/new?offset=0 -- their newest (ksfimport's catalogue
            source).  The archive is /files/<name>.zip; none there is a 404.
A KSF name Momentum lists (catalogue.json's names plus this read) or a Beta
line holds is Momentum's, as in mapwatch; with no catalogue, KSF waits.

It installs with mapwatch's own functions, as mapwatch installs a new name:
Momentum's file at its published SHA1, KSF's archive as one VBSP named for the
map, a .part made world-readable and linked in only while the name is free;
Momentum zones only when they hash to zoneHash, under mapwatch's looks (no
lobby on the map, no run of it); and the map's mapdl.txt row from list_rows,
every other line left as mapwatch wrote it.  Everything else -- builds held,
zones without their hash, _css variants, ports, Beta, approvals, momtracks --
is mapwatch's next run.

It never writes mapwatch's state.json or catalogue.json, never strikes, and
leaves a name mapwatch has struck to mapwatch.  Its own back-off (mapnew.json):
a host that refuses with a status, or whose list does not parse, is held
HOST_HOLD, doubling to HOST_HOLD_MAX, until its next good answer; a file that
fails (404, wrong hash, too big, cut short, not the file, a status-less
refusal) waits FILE_WAIT, doubling to FILE_WAIT_MAX, and is never shelved.
mapwatch's lock is held for the run, and nothing is started after RUN_SECONDS,
so mapwatch's :23 tick finds it free.
"""
import argparse
import faulthandler
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mapwatch as W    # noqa: E402  (imports surfd, quietly)

S = W.S

MOM_HEAD = 100          # newest maps read per Momentum mode, a run: the API's cap
KSF_HEAD = "/api/maps/new?offset=0"
KSF_HEAD_MAX = 100      # their page is 10; more is not that list
HOST_HOLD, HOST_HOLD_MAX = 3600, 6 * 3600
FILE_WAIT, FILE_WAIT_MAX = 6 * 3600, 48 * 3600
RUN_SECONDS = 10 * 60   # cron 28,58: the last start by :08/:38, so mapwatch's :23 finds the lock free
FILE_SECONDS = 600      # one download; mapwatch's 1800 would reach its tick
KSF_WAIT = 60           # for ksfimport's tick; mapwatch waits 300
NEW_MAX, NEW_GB = 5, 2.0
FILE_STATUS = (404, 410, 500)   # the object's own answer: that file waits, the host is not held


class Busy(Exception):
    """ksfimport holds ksf.surf: not asked beside it, nobody's fault."""


def ksf_asked(fn):
    """fn() inside ksfimport's lock (W.ksf_turn); Busy when the crawl keeps it."""
    turn = W.ksf_turn()
    try:
        turn.__enter__()
    except W.Refused as e:
        raise Busy(str(e))
    try:
        return fn()
    finally:
        turn.__exit__(None, None, None)


def mom_head(pacer):
    """-> (rows we could install by lowercased name, every name the heads carry)."""
    rows, names = {}, set()
    for gm, _mode in W.MOM_MODES:
        d = pacer.json("%s/maps?gamemode=%d&take=%d&skip=0&expand=currentVersion"
                       % (W.MOM_API, gm, MOM_HEAD))
        page = d.get("data") if isinstance(d, dict) else None
        total = d.get("totalCount") if isinstance(d, dict) else None
        if not isinstance(page, list) or type(total) is not int or len(page) != min(total, MOM_HEAD):
            raise W.Refused("the map list was not a list -- their format has probably changed")
        for m in page:
            if isinstance(m, dict) and W.okname(m.get("name"), native=True):
                names.add(m["name"].lower())
            r = W.mom_row(m, gm)
            if r:
                rows.setdefault(r["name"].lower(), r)
    return rows, names


def tier_of(pacer, r):
    """A new Momentum row's tier and ranked flag, from its own reply (the head has no
    leaderboards)."""
    d = pacer.json("%s/maps/%d?expand=leaderboards" % (W.MOM_API, r["id"]))
    if not isinstance(d, dict) or d.get("id") != r["id"] or str(d.get("name", "")).lower() != r["name"].lower():
        raise W.Refused("the map's reply is not the map listed")
    r["tier"], r["ranked"], r["boards"] = W.leaderboard_boards(d.get("leaderboards"), r["gamemode"])


def ksf_head(pacer):
    page = pacer.json(W.KSF_BASE + KSF_HEAD)
    if not isinstance(page, list) or len(page) > KSF_HEAD_MAX:
        raise W.Refused("their new-map list was not a list -- their format has probably changed")
    out = {}
    for o in page:
        name = o.get("name") if isinstance(o, dict) else None
        if W.okname(name):
            out.setdefault(name.lower(), {
                "name": name, "mode": "surf" if name.lower().startswith("surf_") else "bhop",
                "tier": o.get("tier") if type(o.get("tier")) is int else None,
                "url": "%s/files/%s.zip" % (W.KSF_BASE, name), "src": "ksf"})
    return out


def ksf_get(state, url, name, part):
    zp = os.path.join(state, "tmp", name + ".zip")
    try:
        got = W.download(url, zp, magic=b"PK")
        return W.zip_bsp(zp, name, part) if got[0] == "ok" else got
    finally:
        W._rm(zp)


def skey(r):
    """mapwatch's key for the file (run's skey): its strikes are read by it."""
    k = r["name"].lower()
    return "%s:ksf" % k if r["src"] == "ksf" else "%s:%s" % (k, r["sha"][:12])


def add_rows(path, maps, inv_new, cat_new, seen, now):
    """mapdl.txt with the new maps' rows; every other line as it was.  -> rows added."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(8 * 1024 * 1024 + 1)
        lines = raw.decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print("  mapdl.txt unreadable (%s): mapwatch's next run lists them" % e)
        return 0
    if len(raw) > 8 * 1024 * 1024 or not lines or not lines[0].startswith("FTESURF-MAPDL 1"):
        print("  mapdl.txt is not mapwatch's list: mapwatch's next run lists them")
        return 0
    rows = W.list_rows(maps, inv_new, cat_new, dict(seen), time.strftime("%Y-%m-%d", time.gmtime(now)),
                       time.strftime("%Y-%m-%d", time.gmtime(now - W.NEW_DAYS * 86400)))
    new = {r.split()[1].lower() for r in rows}
    head = [ln for ln in lines if not ln.startswith("dl ")]
    body = [ln for ln in lines if ln.startswith("dl ") and ln.split()[1].lower() not in new]
    body = sorted(body + rows, key=lambda ln: ln.split()[1].lower())    # list_rows' order
    tmp = path + ".mapnew.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(ln + "\n" for ln in head + body))
    os.replace(tmp, path)
    return len(rows)


def run(a):
    now = int(time.time())
    deadline = now + RUN_SECONDS
    mp = os.path.join(a.state, "mapnew.json")
    me = W._load(mp)
    me = me if isinstance(me, dict) else {}

    def table(key):
        t = me.get(key)
        t = {k: v for k, v in t.items() if isinstance(v, list) and len(v) == 3
             and type(v[0]) in (int, float) and type(v[1]) is int} if isinstance(t, dict) else {}
        me[key] = t
        return t
    hosts = table("hosts")      # host -> [until, refusals, why]
    files = table("files")      # mapwatch's file key -> [until, failures, why]
    for k in [k for k, v in files.items() if now - v[0] > 2 * FILE_WAIT_MAX]:
        del files[k]            # quiet this long: its next failure starts over
    for k in [k for k, v in hosts.items() if now - v[0] > 7 * 86400]:
        del hosts[k]

    mw = W._load(os.path.join(a.state, "state.json"))
    mw = mw if isinstance(mw, dict) else {}
    struck = mw.get("later") if isinstance(mw.get("later"), dict) else {}
    seen = mw.get("seen") if isinstance(mw.get("seen"), dict) else None

    def holding(host):
        h = hosts.get(host)
        return "held until %s (%s)" % (time.strftime("%H:%M UTC", time.gmtime(h[0])), h[2]) \
            if h and now < h[0] else ""

    def hold(host, why):
        n = (hosts.get(host) or [0, 0, ""])[1] + 1
        hosts[host] = [now + min(HOST_HOLD << (n - 1), HOST_HOLD_MAX), n, why[:120]]
        print("  %s refused (%s): held %d min" % (host, why, (hosts[host][0] - now) // 60))

    def wait(key, why):
        n = (files.get(key) or [0, 0, ""])[1] + 1
        files[key] = [now + min(FILE_WAIT << (n - 1), FILE_WAIT_MAX), n, why[:120]]
        print("  %s: %s: waits %d h" % (key, why, (files[key][0] - now) // 3600))

    def waits(key):
        return key in files and now < files[key][0]

    dead = {}                   # host -> why it is done for this run

    def refused(host, e, key=None):
        code = getattr(e, "code", 0) or 0
        if key is not None and (code in FILE_STATUS or not code):
            wait(key, str(e))
        else:
            hold(host, str(e))
        dead[host] = str(e)

    pacer = W.Pacer(a.delay)
    mom, names, ksf, said, read = {}, set(), {}, [], set()
    if holding("api"):
        said.append("momentum: not asked, " + holding("api"))
    else:
        try:
            mom, names = mom_head(pacer)
            read.add("mom")
            hosts.pop("api", None)
        except W.Refused as e:
            refused("api", e)
            said.append("momentum: NOT READ (%s)" % e)
    why = holding("ksf") or W.ksf_parked(now)
    if why:
        said.append("ksf: not asked, " + why)
    else:
        try:
            ksf = ksf_asked(lambda: ksf_head(pacer))
            read.add("ksf")
            hosts.pop("ksf", None)
        except Busy as e:
            said.append("ksf: not asked (%s)" % e)
        except W.Refused as e:
            refused("ksf", e)
            said.append("ksf: NOT READ (%s)" % e)
    cat0 = W._load(os.path.join(a.state, "catalogue.json"))
    cat0 = cat0 if isinstance(cat0, dict) else {}
    catmaps = cat0.get("maps") if isinstance(cat0.get("maps"), dict) else {}
    momnames = cat0.get("momnames")
    extra, _bad = W.extra_list(os.path.join(a.state, "extra.tsv"), os.path.join(a.state, "betaids.tsv"))
    if isinstance(momnames, list):
        momnames = {str(n).lower() for n in momnames} | names
    elif ksf:
        said.append("no reading of Momentum's names (catalogue.json): KSF's new maps wait")
        ksf = {}
    inv, odd = W.inventory(a.maps)
    held = set(inv) | odd
    new = [mom[k] for k in sorted(mom) if k not in held]
    new += [ksf[k] for k in sorted(ksf) if k not in held and k not in momnames and k not in extra]
    todo = [r for r in new if skey(r) not in struck and not waits(skey(r))]
    print("mapnew: heads momentum %d, ksf %d; library %d; new %d (%d mapwatch's, %d waiting)"
          % (len(mom), len(ksf), len(held), len(new),
             sum(skey(r) in struck for r in new), sum(skey(r) not in struck and waits(skey(r)) for r in new)))
    for s in said:
        print("  " + s)
    if not a.go:
        for r in todo[:max(0, a.max)]:
            print("   %-4s %s" % (r["src"], r["name"]))
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        return 0

    W.sweep_leftovers(a.maps, a.state, a.site_zones)    # mapwatch's lock is held
    os.makedirs(os.path.join(a.state, "tmp"), exist_ok=True)
    zdir = os.path.join(a.maps, "zones", "online")
    zidx = W.stems(zdir, ".json")
    gets = {"n": 0, "bytes": 0}
    took, zones, tally = [], [], {}
    hist = {"at": 0.0, "names": None}

    def count(k):
        tally[k] = tally.get(k, 0) + 1

    def quiet(k):
        live = W.live_maps(int(time.time()))
        return live is not None and k not in live

    def unplayed(k, fresh=False):
        if fresh or time.time() - hist["at"] > 60:
            hist["names"], hist["at"] = W.played(), time.time()
        return hist["names"] is not None and k not in hist["names"]

    def first_zones(r, key, name):
        """mapwatch's first zone file for a map it installed, hashed only."""
        zkey = "z:%s:%s" % (key, r["zh"][:12])
        if key in zidx or zkey in struck or waits(zkey) or not (unplayed(key) and quiet(key)):
            return
        try:
            raw, hashed, why = W.zone_fetch(pacer, r)
        except W.Refused as e:
            refused("api", e, zkey)
            return
        except Exception as e:      # mapwatch's rule: one reply must not end every run
            wait(zkey, "%s: %s" % (type(e).__name__, e))
            return
        hosts.pop("api", None)
        if raw is None or not hashed:
            wait(zkey, why or "zones without their hash: mapwatch's")
            return
        if not (quiet(key) and unplayed(key, True) and quiet(key)):
            return
        if W.write_file(os.path.join(zdir, name + ".json"), raw, fresh=True):
            zidx[key] = name
            zones.append(name)
            if a.site_zones and os.path.isdir(a.site_zones) and key not in W.stems(a.site_zones, ".json"):
                W.write_file(os.path.join(a.site_zones, name + ".json"), raw, True)

    for r in todo:
        key, name, fk = r["name"].lower(), r["name"], skey(r)
        host = "ksf" if r["src"] == "ksf" else "cdn"
        if host in dead or holding(host):
            count("%s held or refused: next run" % host)
            continue
        if gets["n"] >= a.max or gets["bytes"] >= a.max_gb * 1e9 or time.time() > deadline:
            count("over this run's budget: next run")
            continue
        if shutil.disk_usage(a.maps).free / 1e9 < W.FLOOR_GB:
            print("under %d GB free: taking nothing" % W.FLOOR_GB)
            break
        if host == "ksf" and W.ksf_parked(int(time.time())):
            dead["ksf"] = "parked"
            continue
        if r["src"] == "mom" and "api" not in dead:
            try:
                tier_of(pacer, r)
                hosts.pop("api", None)
            except W.Refused as e:
                refused("api", e)       # installed all the same; mapwatch's run lists its tier
        if gets["n"]:
            time.sleep(W.GET_DELAY)
        gets["n"] += 1
        part = os.path.join(a.maps, ".mapwatch.%s.part" % name)
        try:
            if host == "cdn":
                got = W.download(r["url"], part, r["sha"], magic=b"VBSP")
            else:
                got = ksf_asked(lambda: ksf_get(a.state, r["url"], name, part))
        except W.Transient as e:
            wait(fk, str(e))
            continue
        except Busy as e:
            dead["ksf"] = str(e)
            continue
        except W.Refused as e:
            refused(host, e, fk)
            continue
        except (W.LocalFault, OSError):
            raise
        except Exception as e:
            wait(fk, "%s: %s" % (type(e).__name__, e))
            continue
        gets["bytes"] += got[-1]
        if got[0] != "ok":
            wait(fk, got[0])
            continue
        hosts.pop(host, None)
        if not W.publish(part, os.path.join(a.maps, name + ".bsp"), True):
            count("the name was taken meanwhile: left")
            continue
        inv[key] = name
        files.pop(fk, None)
        took.append(r)
        print("  installed %s %s %d bytes sha1 %s" % (r["src"], name, got[2], got[1]))
        if r["src"] == "mom" and r["zh"] and r["id"] and "api" not in dead and not holding("api"):
            first_zones(r, key, name)
        W._save(mp, me)

    listed = 0
    if took and seen is not None:
        cat_new = {}
        for r in took:
            k = r["name"].lower()
            c = dict(catmaps.get(k) or {}, name=r["name"], mode=r["mode"])
            src = c.get("src") if isinstance(c.get("src"), str) else ""
            if r["src"] == "ksf":
                c["src"], c["ktier"] = src + ("k" if "k" not in src else ""), r["tier"]
            else:
                c["src"], c["mtier"] = src + ("m" if "m" not in src else ""), r["tier"]
                c["sha"], c["ranked"] = r["sha"], r["ranked"]
            cat_new[k] = c
        W.link_ports(cat_new, inv, momnames if isinstance(momnames, set) else set())
        listed = add_rows(os.path.join(a.state, "mapdl.txt"), a.maps,
                          {r["name"].lower(): r["name"] for r in took}, cat_new, seen, now)
    elif took:
        print("  mapwatch has not listed the library yet: its next run lists them")
    me["last"] = {"at": now, "read": sorted(read), "new": len(new), "took": [r["name"] for r in took]}
    W._save(mp, me)
    print("mapnew: %d request(s), %d download(s); installed %d, zones %d, listed %d%s"
          % (pacer.made, gets["n"], len(took), len(zones), listed,
             "; " + ", ".join("%s %d" % kv for kv in sorted(tally.items())) if tally else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", default=S.MAPS_DIR)
    ap.add_argument("--state", default=os.path.join(S.DATA_DIR, "mapwatch"))
    ap.add_argument("--site-zones", default="",
                    help="also copy a zone file written here when it holds none of that name")
    ap.add_argument("--max", type=int, default=NEW_MAX, help="downloads this run")
    ap.add_argument("--max-gb", type=float, default=NEW_GB)
    ap.add_argument("--delay", type=float, default=W.API_DELAY)
    ap.add_argument("--go", action="store_true", help="fetch; else a plan")
    a = ap.parse_args(argv)
    W.FILE_SECONDS, W.KSF_WAIT = FILE_SECONDS, KSF_WAIT
    W.UA = W.UA.replace(" mapwatch ", " mapnew ")
    lock = W.take_lock(a.state)
    if lock is None:
        print("mapwatch holds %s -- not running beside it" % a.state)
        return 0
    faulthandler.dump_traceback_later(RUN_SECONDS + FILE_SECONDS + 240, exit=True)
    W.be_small()
    try:
        return run(a)
    except (W.LocalFault, OSError) as e:
        print("this box could not read or write (%s): the run ends here" % e)
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
