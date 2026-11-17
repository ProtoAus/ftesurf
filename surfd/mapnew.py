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
            source), only in a run that read Momentum, at most every KSF_EVERY,
            and never within KSF_AFTER_PARK of ksfimport's park: ksf.surf has
            refused our crawl since 11 Nov and Lex asked for less.  The archive
            is /files/<name>.zip; none there is a 404.
A KSF name Momentum lists (catalogue.json's names plus this read) or a Beta
line holds is Momentum's, as in mapwatch; KSF's new maps wait unless mapwatch's
last whole reading (catalogue.json `at`) is under CATALOGUE_FRESH old, since a
late approval can sit past the head and only that reading names it.

It installs with mapwatch's own functions, as mapwatch installs a new name:
Momentum's file at its published SHA1, KSF's archive as one VBSP named for the
map, a .part made world-readable and linked in only while the name is free;
Momentum zones only when they hash to zoneHash, under mapwatch's looks (no
lobby on the map, no run of it).  The map's mapdl.txt row comes from
list_rows over mapwatch's catalogue plus this read, every other line left as
mapwatch wrote it.  The same entry goes into catalogue.json when the catalogue
has none and the entry is whole (a Momentum map whose tier its reply gave), so
a mapwatch run that cannot read a list still lists it; mapwatch keeps such
entries until its next whole reading replaces them.  A row not yet written (a
run cut short, an unreadable list) is owed in mapnew.json and written by a
later run -- unless mapwatch has read both lists since, when its row stands.  Everything else -- builds held, zones
without their hash, _css variants, Beta, approvals, momtracks -- is mapwatch's.

It never writes mapwatch's state.json, never strikes, and leaves a name
mapwatch has struck to mapwatch.  Its own back-off (mapnew.json), timed from
the refusal: a host that refuses with a status, or whose list does not parse,
is held HOST_HOLD, doubling to HOST_HOLD_MAX, and starts over only after
HOST_FORGET with no refusal (Momentum's API, its CDN, KSF's list and KSF's
archives are four hosts); a holds table mapwatch keeps is honoured too.  A
file whose fetch fails in any way waits FILE_WAIT, doubling to FILE_WAIT_MAX,
so the next run tries the others first; it is never shelved.  The request in
flight is recorded first, so a run ended inside one (KILL_SECONDS, a reply
that never ends) counts as that host's refusal and that file's failure.  A dry
run asks the lists too, and keeps what they answered.  mapwatch's lock is held for the run,
nothing is started after RUN_SECONDS, and the process ends at KILL_SECONDS, so
mapwatch's :23 tick finds the lock free.
"""
import argparse
import contextlib
import faulthandler
import math
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
KSF_EVERY = 2 * 3600    # between asks of KSF's head, refused or not
CATALOGUE_FRESH = 7 * 3600   # mapwatch's last whole reading, for KSF's names: one 6-h tick and slack
KSF_AFTER_PARK = 6 * 3600   # after ksfimport's park ends, its own tick retries first
HOST_HOLD, HOST_HOLD_MAX = 3600, 6 * 3600
HOST_FORGET = 2 * HOST_HOLD_MAX     # quiet this long after a hold, the next refusal starts over
FILE_WAIT, FILE_WAIT_MAX = 6 * 3600, 48 * 3600
KSF_GONE = 7 * 86400    # a KSF archive that is not there (mapwatch reads KSF's links; this list has none)
RUN_SECONDS = 8 * 60    # cron 28,58: no step starts after :06/:36
FILE_SECONDS = 420      # one download's body (mapwatch: 1800)
REPLY_SECONDS = 60      # a reply's headers, and a small reply's body (mapwatch: 120 each)
KILL_SECONDS = RUN_SECONDS + FILE_SECONDS + 6 * REPLY_SECONDS   # the last step: tier, file, zones -> :19/:49
KSF_WAIT = 60           # for ksfimport's tick; mapwatch waits 300
NEW_MAX, NEW_GB = 5, 2.0
FILE_STATUS = (404, 410, 500)   # the object's own answer: the host is not held


class Busy(Exception):
    """ksf.surf is not to be asked now (ksfimport's tick or park): nobody's fault."""


def ksf_park(now):
    why = W.ksf_parked(now - KSF_AFTER_PARK)
    return why and why + ", and %d h for its own retry" % (KSF_AFTER_PARK // 3600)


def ksf_asked(fn):
    """fn() inside ksfimport's lock (W.ksf_turn), the park read again once it is held."""
    try:
        import fcntl            # noqa: F401  (W.ksf_turn runs unlocked where its lock cannot open)
        open(W.KSF_LOCK, "a").close()
    except ImportError:
        pass
    except OSError as e:
        raise Busy("its lock cannot be opened (%s)" % e)
    turn = W.ksf_turn()
    try:
        turn.__enter__()
    except W.Refused as e:
        raise Busy(str(e))
    try:
        why = ksf_park(int(time.time()))
        if why:
            raise Busy(why)
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
    r["whole"] = True


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
    """-> (zip_bsp's answer, the archive's bytes on the wire)."""
    zp = os.path.join(state, "tmp", name + ".zip")
    try:
        got = W.download(url, zp, magic=b"PK")
        if got[0] != "ok":
            return got, got[-1]
        return W.zip_bsp(zp, name, part), got[2]
    finally:
        W._rm(zp)


def skey(r):
    """mapwatch's key for the file (run's skey): its strikes are read by it."""
    k = r["name"].lower()
    return "%s:ksf" % k if r["src"] == "ksf" else "%s:%s" % (k, r["sha"][:12])


def entry(r, had):
    """The catalogue entry mapwatch builds for list row `r`, over the one it had; `whole`
    (mapnew's own, not written to the catalogue) when nothing in it is a guess."""
    c = dict(had if isinstance(had, dict) else {}, name=r["name"], mode=r["mode"])
    src = c.get("src") if isinstance(c.get("src"), str) else ""
    if r["src"] == "ksf":
        c["src"], c["ktier"] = src + ("k" if "k" not in src else ""), r["tier"]
    else:
        c["src"], c["mtier"] = src + ("m" if "m" not in src else ""), r["tier"]
        c["sha"], c["ranked"] = r["sha"], r["ranked"]
    c["whole"] = r["src"] == "ksf" or bool(r.get("whole"))
    return c


def dl_key(ln):
    f = ln.split()
    return f[1].lower() if len(f) > 1 else ""


def add_rows(path, maps, inv, cat, keys, seen, now, skip=()):
    """mapdl.txt with the rows of `keys` written from `cat` (but not those of `skip` that
    already have one); every other line as it was.  -> the keys written, or None."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(8 * 1024 * 1024 + 1)
        lines = raw.decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print("  mapdl.txt unreadable (%s): its rows are owed" % e)
        return None
    if len(raw) > 8 * 1024 * 1024 or not lines or not lines[0].startswith("FTESURF-MAPDL 1"):
        print("  mapdl.txt is not mapwatch's list: its rows are owed")
        return None
    have = {dl_key(ln) for ln in lines if ln.startswith("dl ")}
    keys = {k for k in keys if k not in skip or k not in have}
    # The whole library, so a port's `of` finds its base; only `keys`' rows are taken.
    rows = [r for r in W.list_rows(maps, inv, cat, dict(seen), time.strftime("%Y-%m-%d", time.gmtime(now)),
                                   time.strftime("%Y-%m-%d", time.gmtime(now - W.NEW_DAYS * 86400)))
            if dl_key(r) in keys]
    done = {dl_key(r) for r in rows}
    head = [ln for ln in lines if not ln.startswith("dl ")]
    body = [ln for ln in lines if ln.startswith("dl ") and dl_key(ln) not in done]
    body = sorted(body + rows, key=dl_key)          # list_rows' order
    tmp = path + ".mapnew.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(ln + "\n" for ln in head + body))
    os.replace(tmp, path)
    return keys


def note_catalogue(path, cat, keys, names):
    """catalogue.json with the whole entries of `keys` it has none for, and Momentum's
    `names`, added; mapwatch's next whole reading replaces it."""
    doc = W._load(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("maps"), dict) or not isinstance(doc.get("momnames"), list):
        return
    for k in keys:
        c = cat.get(k)
        if isinstance(c, dict) and c.get("whole") and k not in doc["maps"]:
            doc["maps"][k] = {f: v for f, v in c.items() if f != "whole"}
    doc["momnames"] = sorted({str(n) for n in doc["momnames"]} | names)
    W._save(path, doc)


def run(a):
    mp = os.path.join(a.state, "mapnew.json")
    me = W._load(mp)
    me = me if isinstance(me, dict) else {}
    try:
        return tick(a, me, mp)
    finally:
        try:
            W._save(mp, me)         # a dry run asks the lists too: their answers are kept
        except OSError as e:
            print("  mapnew.json could not be saved (%s)" % e)


def tick(a, me, mp):
    now = int(time.time())
    deadline = now + RUN_SECONDS

    def table(key, ok):
        t = me.get(key)
        t = {k: v for k, v in t.items() if ok(v)} if isinstance(t, dict) else {}
        me[key] = t
        return t

    def when(v, ahead=7 * 86400):
        return type(v) in (int, float) and math.isfinite(v) and 0 <= v <= now + ahead

    def held_shape(v, most=64):
        return (isinstance(v, list) and len(v) == 3 and when(v[0], math.inf) and type(v[1]) is int
                and 1 <= v[1] <= most and isinstance(v[2], str))
    hosts = table("hosts", held_shape)      # host -> [until, refusals, why]
    files = table("files", held_shape)      # mapwatch's file key -> [until, failures, why]
    owed = table("owed", lambda v: isinstance(v, dict) and when(v.get("at"), math.inf)
                 and isinstance(v.get("c"), dict) and isinstance(v["c"].get("name"), str))
    # A clock stepped back, or a hand edit, holds no longer than the longest hold; nothing is dropped.
    for t, most in ((hosts, HOST_HOLD_MAX), (files, max(FILE_WAIT_MAX, KSF_GONE))):
        for v in t.values():
            v[0] = min(v[0], now + most)
    for o in owed.values():
        o["at"] = min(o["at"], now)
    for k in [k for k, v in files.items() if now - v[0] > 2 * FILE_WAIT_MAX]:
        del files[k]            # quiet this long: its next failure starts over
    for k in [k for k, v in hosts.items() if now - v[0] > HOST_FORGET]:
        del hosts[k]

    mw = W._load(os.path.join(a.state, "state.json"))
    mw = mw if isinstance(mw, dict) else {}
    struck = mw.get("later") if isinstance(mw.get("later"), dict) else {}
    seen = mw.get("seen") if isinstance(mw.get("seen"), dict) else None
    mwhosts = {k: [min(v[0], now + 86400), v[1], v[2]] for k, v in mw.get("hosts").items() if held_shape(v, 10 ** 6)} \
        if isinstance(mw.get("hosts"), dict) else {}     # main's mapwatch keeps one; live has none

    def holding(host):
        for t in (hosts, mwhosts):
            h = t.get(host)
            if h and time.time() < h[0]:
                return "held until %s (%s)" % (time.strftime("%H:%M UTC", time.gmtime(h[0])), h[2])
        return ""

    def hold(host, why):
        n = min((hosts.get(host) or [0, 0, ""])[1], 63) + 1
        secs = min(HOST_HOLD << min(n - 1, 16), HOST_HOLD_MAX)
        hosts[host] = [int(time.time()) + secs, n, why[:120]]
        print("  %s refused (%s): held %d min" % (host, why, secs // 60))

    def wait(key, why, floor=0):
        n = min((files.get(key) or [0, 0, ""])[1], 63) + 1
        secs = max(floor, min(FILE_WAIT << min(n - 1, 16), FILE_WAIT_MAX))
        files[key] = [int(time.time()) + secs, n, why[:120]]
        print("  %s: %s: waits %d h" % (key, why, secs // 3600))

    def waits(key):
        return key in files and now < files[key][0]

    dead = {}                   # host -> why it is done for this run

    def refused(host, e, key=None):
        """The host is done for the run; held when the refusal is its; the file waits."""
        code = getattr(e, "code", 0) or 0
        if key is None or (code and code not in FILE_STATUS):
            hold(host, str(e))
        if key is not None:
            wait(key, str(e))
        dead[host] = str(e)

    @contextlib.contextmanager
    def asking(host, key=None):
        """The request in flight, saved before it is made (see the docstring)."""
        me["asking"] = [host, key]
        W._save(mp, me)
        try:
            yield
        finally:
            me.pop("asking", None)

    prev = me.pop("asking", None)
    if (isinstance(prev, list) and len(prev) == 2 and prev[0] in ("api", "cdn", "ksf", "ksfdl")
            and (prev[1] is None or isinstance(prev[1], str))):
        hold(prev[0], "the last run was ended inside its request")
        if prev[1]:
            wait(prev[1], "the last run was ended inside its request")

    pacer = W.Pacer(a.delay)
    mom, names, ksf, said, read = {}, set(), {}, [], set()
    if holding("api"):
        said.append("momentum: not asked, " + holding("api"))
    else:
        try:
            with asking("api"):
                mom, names = mom_head(pacer)
            read.add("mom")
        except W.Refused as e:
            refused("api", e)
            said.append("momentum: NOT READ (%s)" % e)
    cp = os.path.join(a.state, "catalogue.json")
    cat0 = W._load(cp)
    cat0 = cat0 if isinstance(cat0, dict) else {}
    catmaps = cat0.get("maps") if isinstance(cat0.get("maps"), dict) else {}
    cat_at = cat0.get("at") if when(cat0.get("at"), 60) else 0
    momnames = {str(n).lower() for n in cat0["momnames"]} | names \
        if isinstance(cat0.get("momnames"), list) else None
    extra, _bad = W.extra_list(os.path.join(a.state, "extra.tsv"), os.path.join(a.state, "betaids.tsv"))
    last = min(me["ksf_at"], now) if when(me.get("ksf_at"), math.inf) else 0    # stepped back: the gap stands
    why = ("Momentum was not read: KSF's names wait" if "mom" not in read else
           "mapwatch's last whole reading of Momentum's names is %s: KSF's names wait"
           % ("missing" if momnames is None else "%d h old" % ((now - cat_at) // 3600))
           if momnames is None or now - cat_at > CATALOGUE_FRESH else
           holding("ksf") or ksf_park(now) or
           ("asked %d min ago" % ((now - last) // 60) if now - last < KSF_EVERY else ""))
    if why:
        said.append("ksf: not asked, " + why)
    else:
        me["ksf_at"] = now          # before the ask: a run that dies in it keeps the gap
        try:
            with asking("ksf"):
                ksf = ksf_asked(lambda: ksf_head(pacer))
            read.add("ksf")
        except Busy as e:
            me["ksf_at"] = last
            said.append("ksf: not asked (%s)" % e)
        except W.Refused as e:
            refused("ksf", e)
            said.append("ksf: NOT READ (%s)" % e)
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
            with asking("api", zkey):
                raw, hashed, why = W.zone_fetch(pacer, r)
        except W.Refused as e:
            refused("api", e, zkey)
            return
        except Exception as e:      # mapwatch's rule: one reply must not end every run
            wait(zkey, "%s: %s" % (type(e).__name__, e))
            return
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
        hostset = ("ksf", "ksfdl") if r["src"] == "ksf" else ("cdn",)
        host = hostset[-1]
        if any(h in dead or holding(h) for h in hostset):
            count("%s held or refused: next run" % host)
            continue
        if gets["n"] >= a.max or gets["bytes"] >= a.max_gb * 1e9 or time.time() > deadline:
            count("over this run's budget: next run")
            continue
        if shutil.disk_usage(a.maps).free / 1e9 < W.FLOOR_GB:
            print("under %d GB free: taking nothing" % W.FLOOR_GB)
            break
        if r["src"] == "mom" and "api" not in dead:
            try:
                with asking("api"):
                    tier_of(pacer, r)
            except W.Refused as e:
                if e.code and e.code not in FILE_STATUS:
                    refused("api", e)       # installed all the same, its tier left to mapwatch
                else:
                    print("  %s: its tier (%s): left to a mapwatch run that reads Momentum" % (name, e))
        if gets["n"]:
            time.sleep(W.GET_DELAY)
        gets["n"] += 1
        part = os.path.join(a.maps, ".mapwatch.%s.part" % name)
        try:
            with asking(host, fk):
                if host == "cdn":
                    got = W.download(r["url"], part, r["sha"], magic=b"VBSP")
                    wire = got[-1]
                else:
                    got, wire = ksf_asked(lambda: ksf_get(a.state, r["url"], name, part))
        except W.Transient as e:
            wait(fk, str(e))
            continue
        except Busy as e:
            dead["ksfdl"] = str(e)
            continue
        except W.Refused as e:
            refused(host, e, fk)
            continue
        except (W.LocalFault, OSError):
            raise
        except Exception as e:
            wait(fk, "%s: %s" % (type(e).__name__, e))
            continue
        gets["bytes"] += wire
        if got[0] != "ok":
            wait(fk, got[0], KSF_GONE if got[0] == "gone" and host == "ksfdl" else 0)
            continue
        try:
            put = W.publish(part, os.path.join(a.maps, name + ".bsp"), True)
        except Exception as e:      # tascontent's lease, a disk: not every run's download again
            W._rm(part)
            wait(fk, "publish: %s: %s" % (type(e).__name__, e))
            if isinstance(e, (W.LocalFault, OSError)):
                raise
            continue
        if not put:
            count("the name was taken meanwhile: left")
            continue
        inv[key] = name
        files.pop(fk, None)
        owed[key] = {"at": now, "c": entry(r, catmaps.get(key))}
        took.append(r)
        print("  installed %s %s %d bytes sha1 %s" % (r["src"], name, got[2], got[1]))
        W._save(mp, me)
        if r["src"] == "mom" and r["zh"] and r["id"] and "api" not in dead and not holding("api"):
            first_zones(r, key, name)

    listed = 0
    for k in [k for k in owed if k not in inv]:
        del owed[k]                 # gone from the library since
    if owed and seen is None:
        print("  mapwatch has not listed the library yet: its next run lists %d map(s)" % len(owed))
    elif owed:
        # mapwatch's whole reading since the install is newer than what was owed: its entry
        # (and a row it wrote) stands.
        since = {k for k, o in owed.items() if cat_at > o["at"]}
        cat = dict(catmaps, **{k: dict(o["c"]) for k, o in owed.items() if k not in since or k not in catmaps})
        W.link_ports(cat, inv, (momnames or set()) | set(extra))
        keys = add_rows(os.path.join(a.state, "mapdl.txt"), a.maps, inv, cat, set(owed), seen, now, skip=since)
        if keys is not None:
            note_catalogue(cp, cat, keys - since, names)
            listed = len(keys)
            owed.clear()
    me["last"] = {"at": now, "read": sorted(read), "new": len(new), "took": [r["name"] for r in took]}
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
    W.OPEN_SECONDS = W.API_SECONDS = REPLY_SECONDS
    W.UA = W.UA.replace(" mapwatch ", " mapnew ")
    lock = W.take_lock(a.state)
    if lock is None:
        print("mapwatch holds %s -- not running beside it" % a.state)
        return 0
    faulthandler.dump_traceback_later(KILL_SECONDS, exit=True)
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
