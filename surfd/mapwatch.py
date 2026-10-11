"""Keep the map library level with Momentum's and KSF's own lists.

  python3 mapwatch.py [--go] [--variants N] [--site-zones DIR] [--updates]   (cron)

Lex, 11 Oct 2026: every KSF map and every Momentum surf/bhop map, "or future
maps they add, so we need rescanning, and downloading of new maps".  The
6-hourly Windows sweep (tools/mapscan.py) lists what exists, fetches nothing
and is missed while that PC is off; this runs on the box that serves the maps.

WHAT IT READS, each anonymous:
  Momentum   /v1/maps?gamemode=1|2&expand=currentVersion,leaderboards --
             APPROVED maps only (ranked and unranked boards; a submission
             answers 401).  A row names its BSP's SHA1 (bspHash), its URL on
             the CDN and its zones' SHA1 (zoneHash).
  KSF        https://ksf.surf/maps -- the page embeds the whole list (952 on
             11 Oct, where the Drive sheet stops at 929) with a tier and
             /files/<map>.zip, one bare .bsp.
  extra.tsv  <state>/extra.tsv, `name sha1 url` a line: Momentum's Beta maps,
             from the game's own cache on a PC that has it (tools/mapscan.py
             pushes it).  Without that PC the Beta list stays as it was.

WHAT IT INSTALLS: a map whose NAME the library does not hold.  A Momentum file
is kept only when its SHA1 is the one its row publishes -- the row and the hash
come from one API, so that proves the transfer, not the API.  A KSF archive is
kept only when it holds exactly one .bsp, named for the map, with a VBSP
header; nothing publishes a digest for it, so its build is `unknown`, as
maproster.py says of every CS:S map.  Both are written as .part, made
world-readable (importing surfd sets umask 077; nginx serves this directory)
and linked into place only while the name is still free.

ZONES ARE THE TIMING RULE, so they are written narrowly: Momentum's own, from
/v1/maps/<id>?expand=currentVersionWithZones, only when the bytes hash to
zoneHash (the file the game writes: surf_skyhaven, 7,407 bytes, the same SHA1),
only for a map held AT THE BUILD that row publishes (zones are world
coordinates), never under maps/zones/local, which the server reads first, and
never while a lobby is on the map or the lobbies cannot be heard.  A name that
already has a native run, a save, a parked run or kept evidence gets its FIRST
zone file only with --updates -- a map installed this run included (a BSP that
was lost and comes back has its runs still): that file changes its zone crc,
and with it what a parked run resumes to.

TWO BUILDS OF ONE NAME (--variants N).  A name both list holds Momentum's
build, and KSF's records were set on KSF's.  N of KSF's archives a run are
compared with the file held, and one that differs is kept as <name>_css: its
own name, so its own download, zones and board (ROADMAP 8).  KSF's archive and
not a CS:S install's copy: on 11 Oct a PC's cstrike build was KSF's on 3 of 6
maps.  It gets no zones here; donating the plain build's is
tools/zoneinstall.py's measured step.

A BUILD OR A ZONE FILE THAT DIFFERS from the published one is REPORTED and left
alone without --updates: the runs on that map's board were set on what it
replaces, and nothing reads the old build back.  With it (approved maps only,
never from extra.tsv) the old build is linked to <maps>/.old/<name>.<sha1
12>.bsp, the new one goes in with its zones or not at all, and a map some
lobby is on -- or might be: a lobby silent, the table empty or unreadable --
waits, asked before the download and again before the swap.  The two renames
are not one step, and a lobby can still change onto the map between the last
look and the swap.

POLITE: one mapwatch at a time, one request at a time, API_DELAY apart, every
download GET_DELAY after the last, --max downloads and --max-gb a run, nothing
below FLOOR_GB free, nothing started after RUN_SECONDS.  A refusal ends that
host for the run and nothing is retried in it: cron's cadence is the backoff.
What is counted against a FILE (STRIKES, then left for RETRY_DAYS) is what
only that file can be: a 404/410, its own 500, a BSP with the wrong hash, an
archive that is one and is wrong, zones that are zones and hash wrong.  A 403,
429, 502-504, no answer, or a 200 that is not a BSP, an archive or zones at
all (a block page) is the host's: no strike, and the file goes to the back of
the next run.  A transfer cut short is nobody's strike either.
"""
import argparse
import contextlib
import faulthandler
import hashlib
import http.client
import io
import json
import logging
import os
import re
import shutil
import signal
import struct
import sys
import time
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Importing surfd logs "surfd ready", which reads as a restart on every tick
# (sweep.py's fix).
if not logging.getLogger("surfd").handlers:
    _quiet = logging.StreamHandler(sys.stderr)
    _quiet.setLevel(logging.WARNING)
    logging.getLogger("surfd").addHandler(_quiet)

import surfd as S       # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOM_API = "https://api.momentum-mod.org/v1"
MOM_CDN = "https://cdn.momentum-mod.org/maps/"
KSF_BASE = "https://ksf.surf"
UA = "FTESurf/0.1 mapwatch (+https://proto.bar/ftesurf)"

MOM_MODES = ((1, "surf"), (2, "bhop"))      # Momentum's gamemode ids
MOM_TAKE = 100                              # the API's own cap
MOM_PAGES = 40                              # a list longer than this is not theirs
MOM_MIN = 150           # surf_/bhop_ names a gamemode's list must hold (383 and 375)
KSF_MIN = 400           # fewer maps than this is a page we failed to read (952)
KSF_MAX = 5000          # ...and more is not their list either
API_DELAY = 1.5         # s between requests; 1.0 tripped Momentum's 429 (momfetch)
GET_DELAY = 2.0         # s between downloads
TIMEOUT = 60
WATCH_MAX = 40          # downloads a run
WATCH_GB = 6.0          # ...and bytes
ZONES_MAX = 40          # zone requests a run
MAX_MAP_BYTES = 1 << 30     # the largest BSP known is 335 MB
MAX_API_BYTES = 6 << 20     # a list page is 1.4 MB, ksf.surf/maps 0.8 MB; parsed, a
                            # megabyte of empty rows is tens of megabytes of objects
MAX_ZIP_FILES = 64          # KSF's archives hold one file
MAX_MEM = 1536 << 20        # this process's address space: a reply at the cap parses
                            # to ~200 MB, a run's own work is under 100
FILE_SECONDS = 1800     # one download: a host dripping bytes must not hold the lock
OPEN_SECONDS = 120      # until a reply's headers: no read clock covers that wait
KSF_LOCK = "/tmp/surfd-ksfwatch.lock"   # what the crawl's cron line holds for a tick
KSF_WAIT = 300          # s to wait for that tick to end before leaving KSF for the run
API_SECONDS = 120       # ...nor one reply
RUN_SECONDS = 3 * 3600  # nothing is started after this; cron runs it again
FLOOR_GB = 20           # momgrab's floor on the same disk
STRIKES = 3
RETRY_DAYS = 30
VARIANT = "_css"        # one of mapmeta.py's ALIAS_SUFFIXES: tier, picture and group follow
WANT_DAYS = 14          # ksfimport's: a map viewed this recently goes first

# fullmatch, never match with a `$`: that passes "name\n".
HEX40 = re.compile(r"[0-9a-f]{40}")
CDN_LEAF = re.compile(r"[0-9a-f-]{36}\.bsp")
# What nginx's map rule and the engine's downloadmap both take.  The RAW name
# is tested, because it is the raw name that becomes a path and a url.
NAME_OK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
PREFIX = ("surf_", "bhop_")


class Refused(Exception):
    """A host said no, or did not answer: nothing more is asked of it this run.
    `code` is the HTTP status when there was one."""

    def __init__(self, msg, code=0):
        Exception.__init__(self, msg)
        self.code = code


class Stalled(Refused):
    """No reply's headers within OPEN_SECONDS."""

    def __init__(self):
        Refused.__init__(self, "no reply in %d s" % OPEN_SECONDS)


class Transient(Exception):
    """This file's transfer broke off: counted against the file, tried later."""


def okname(name):
    return (isinstance(name, str) and NAME_OK.fullmatch(name) is not None
            and name.lower().startswith(PREFIX))


def okcdn(url):
    return (isinstance(url, str) and url.startswith(MOM_CDN)
            and CDN_LEAF.fullmatch(url[len(MOM_CDN):]) is not None)


def own_fault(code):
    """A status that is about the object asked for rather than about us or the
    host: a 500 from its own handler.  502/503/504 are a gateway's."""
    return code == 500


def _load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _save(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc))
    os.replace(tmp, path)


def _rm(p):
    try:
        os.remove(p)
    except FileNotFoundError:
        pass


def take_lock(d):
    """One mapwatch at a time: two would write one .part."""
    os.makedirs(d, exist_ok=True)
    fh = io.open(os.path.join(d, ".lock"), "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


# --------------------------------------------------------------------------
# the wire: every request goes through opener(), which tests replace

def opener(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=TIMEOUT)


def opened(url):
    """opener(url) with the wait for the reply bounded.  The read clocks start
    at the first body byte and the socket timeout restarts at every byte, so a
    host dripping HEADERS was in neither, and held the lock against every later
    run.  SIGALRM, so Linux; elsewhere the socket timeout alone."""
    if not hasattr(signal, "SIGALRM"):
        return opener(url)

    def late(_sig, _frame):
        raise Stalled()
    old = signal.signal(signal.SIGALRM, late)
    signal.alarm(OPEN_SECONDS)
    try:
        return opener(url)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


@contextlib.contextmanager
def ksf_turn():
    """One of us at a time on ksf.surf.  ksfimport --watch crawls it every five
    minutes under KSF_LOCK, and a refusal parks that crawl for six hours,
    doubling: on 11 Oct its request timed out while the first fill was
    downloading archives beside it.  Held for one request; the crawl's
    `flock -n` skips a tick that starts meanwhile.  Linux only."""
    try:
        import fcntl
        fh = open(KSF_LOCK, "a")
    except (ImportError, OSError):
        fh = None
    try:
        t0 = time.time()
        while fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() - t0 >= KSF_WAIT:
                    raise Refused("its crawl is on it: not asked beside that")
                time.sleep(2)
        yield
    finally:
        if fh is not None:
            fh.close()


def ksf_parked(now):
    """-> why KSF must not be asked now, or "".  The crawl's own rule is that a
    refusal is not retried until its park ends; a second tool asking the same
    host in that time is the retry."""
    park = _load(os.path.join(S.DATA_DIR, "ksf", ".refused"))
    if isinstance(park, dict) and type(park.get("until")) in (int, float) and now < park["until"]:
        return "it refused its crawl (%s): nothing asked until %s" % (
            str(park.get("why"))[:80],
            time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(park["until"])))
    return ""


class Pacer:
    """One request at a time, `delay` apart, counted."""

    def __init__(self, delay):
        self.delay, self.made = delay, 0

    def text(self, url):
        if self.made:
            time.sleep(self.delay)
        self.made += 1
        body, t0 = [], time.time()
        try:
            with opened(url) as r:
                if r.status != 200:
                    raise Refused("HTTP %s" % r.status, r.status or 0)
                # read1: one recv at a time, so the cap and the clock are both
                # looked at; read(n) waits for all n from a host dripping bytes.
                while True:
                    b = r.read1(1 << 16)
                    if not b:
                        break
                    body.append(b)
                    if sum(map(len, body)) > MAX_API_BYTES:
                        raise Refused("a reply over %d MB" % (MAX_API_BYTES >> 20))
                    if time.time() - t0 > API_SECONDS:
                        raise Refused("a reply slower than %d s" % API_SECONDS)
        except urllib.error.HTTPError as e:
            raise Refused("HTTP %d" % e.code, e.code)
        except urllib.error.URLError as e:
            raise Refused(str(e.reason))
        except (OSError, http.client.HTTPException, ValueError) as e:
            raise Refused("no answer: %s" % (str(e) or type(e).__name__))
        return b"".join(body).decode("utf-8", "replace")

    def json(self, url):
        try:
            return json.loads(self.text(url))
        except (ValueError, RecursionError):
            raise Refused("the reply did not parse -- their format has probably changed")
        except MemoryError:
            raise Refused("the reply was too much to parse")


def download(url, part, want_sha=None, cap=MAX_MAP_BYTES, magic=b""):
    """Fetch `url` to `part`.  -> ("ok", sha1, bytes), ("gone", 0), ("toobig", n)
    or ("badhash", n); `part` exists only after "ok".  Raises Transient for a
    transfer cut short or slower than FILE_SECONDS, and Refused for a refusal --
    which a 200 whose body does not begin with `magic` is: a block page is not
    a bad map, and must not be counted against the map.  A fault of this disk
    is a LocalFault."""
    n, sha, big, t0, head = 0, hashlib.sha1(), False, time.time(), b""
    try:
        os.makedirs(os.path.dirname(part), exist_ok=True)
        fh = open(part, "wb")
    except OSError as e:
        raise LocalFault(e)
    try:
        with fh:
            try:
                with opened(url) as r:
                    if r.status != 200:
                        raise Refused("HTTP %s" % r.status, r.status or 0)
                    want = str(r.headers.get("Content-Length") or "")
                    while True:
                        b = r.read1(1 << 18)    # see Pacer.text
                        if not b:
                            break
                        if len(head) < 8:
                            head += b[:8]
                            # A page in a file's place is not read to its end.
                            if len(head) >= len(magic) and not head.startswith(magic):
                                raise Refused("a 200 that is not the file asked for")
                        n += len(b)
                        if n > cap:
                            big = True
                            break
                        if time.time() - t0 > FILE_SECONDS:
                            raise Transient("too slow: %d bytes in %d s" % (n, FILE_SECONDS))
                        sha.update(b)
                        try:
                            fh.write(b)
                        except OSError as e:
                            raise LocalFault(e)
            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    return ("gone", 0)
                raise Refused("HTTP %d" % e.code, e.code)
            except urllib.error.URLError as e:
                raise Refused(str(e.reason))
            except http.client.IncompleteRead:
                raise Transient("cut short")
            except (OSError, http.client.HTTPException, ValueError) as e:
                raise Refused("no answer: %s" % (str(e) or type(e).__name__))
        if big:
            return ("toobig", n)
        if want.isdigit() and n != int(want):
            raise Transient("cut short at %d of %s bytes" % (n, want))
        if not head.startswith(magic):
            raise Refused("a 200 that is not the file asked for (%d bytes)" % n)
        if want_sha is not None and sha.hexdigest() != want_sha:
            return ("badhash", n)
        big = None                      # the one way out that keeps the file
        return ("ok", sha.hexdigest(), n)
    finally:
        if big is not None:
            _rm(part)


class LocalFault(Exception):
    """This box could not write: nobody's strike, and the run ends."""


# --------------------------------------------------------------------------
# the lists

def mom_row(m):
    """One /v1/maps row as a catalogue row, or None when it is not a surf/bhop
    map we could install."""
    if not isinstance(m, dict):
        return None
    name = m.get("name")
    if not okname(name) or type(m.get("id")) is not int:
        return None
    cv = m.get("currentVersion")
    cv = cv if isinstance(cv, dict) else {}
    sha, url = str(cv.get("bspHash") or "").lower(), cv.get("downloadURL")
    if not HEX40.fullmatch(sha) or not okcdn(url):
        return None
    zh = str(cv.get("zoneHash") or "").lower()
    mode = "surf" if name.lower().startswith("surf_") else "bhop"
    gm = 1 if mode == "surf" else 2
    tier, ranked = None, None
    lbs = m.get("leaderboards")
    for lb in lbs if isinstance(lbs, list) else []:
        if (isinstance(lb, dict) and lb.get("gamemode") == gm and lb.get("trackType") == 0
                and lb.get("trackNum") == 1 and lb.get("style") == 0):
            tier = lb.get("tier") if type(lb.get("tier")) is int else None
            ranked = lb.get("type") == 0
    return {"name": name, "id": m["id"], "sha": sha, "url": url, "mode": mode,
            "zh": zh if HEX40.fullmatch(zh) else None, "tier": tier, "ranked": ranked,
            "src": "mom"}


def mom_list(pacer):
    """-> (rows we could install, by lowercased name; EVERY surf/bhop name the
    list carries).  The second is what decides whose build a name gets, and a
    row we cannot use is still Momentum's name."""
    rows, names = {}, set()
    for gm, _mode in MOM_MODES:
        skip, seen = 0, set()       # distinct: a host ignoring `skip` repeats a page
        for _ in range(MOM_PAGES):
            d = pacer.json("%s/maps?gamemode=%d&take=%d&skip=%d"
                           "&expand=currentVersion,leaderboards"
                           % (MOM_API, gm, MOM_TAKE, skip))
            page = d.get("data") if isinstance(d, dict) else None
            total = d.get("totalCount") if isinstance(d, dict) else None
            if not isinstance(page, list) or type(total) is not int:
                raise Refused("the map list was not a list -- their format has "
                              "probably changed")
            if len(page) > MOM_TAKE:    # every name is kept: 40 pages of ANY size are not
                raise Refused("a page of %d maps where %d were asked for"
                              % (len(page), MOM_TAKE))
            for m in page:
                if isinstance(m, dict) and okname(m.get("name")):
                    names.add(m["name"].lower())
                    seen.add(m["name"].lower())
                r = mom_row(m)
                if r:
                    rows.setdefault(r["name"].lower(), r)
            skip += len(page)
            if skip >= total:
                break
            if not page:
                raise Refused("the map list ended at %d of %d" % (skip, total))
        else:
            raise Refused("the map list ran past %d pages" % MOM_PAGES)
        if len(seen) < MOM_MIN:
            raise Refused("only %d maps in gamemode %d -- their format has "
                          "probably changed" % (len(seen), gm))
    return rows, names


def next_chunks(html):
    """The string literals of a page's self.__next_f.push([1,"..."]) calls,
    decoded.  A scan: the regex for an escaped string cost ~280 MB of working
    set per megabyte of one chunk (the review's measurement)."""
    out, at, mark = [], 0, 'self.__next_f.push([1,"'
    while True:
        i = html.find(mark, at)
        if i < 0:
            return out
        i += len(mark) - 1          # at the opening quote
        j = i + 1
        while True:
            j = html.find('"', j)
            if j < 0:
                return out          # no closing quote: the page was cut
            k = j - 1
            while html[k] == "\\":
                k -= 1
            if (j - 1 - k) % 2 == 0:
                break               # not an escaped quote
            j += 1
        try:
            out.append(json.loads(html[i:j + 1]))
        except ValueError:
            pass
        at = j + 1


def ksf_list(pacer):
    """KSF's map list out of its /maps page: the rows ride in the page's Next.js
    payload as {"mapID":..,"name":..,"tier":..,"link":"/files/<name>.zip"}."""
    html = pacer.text(KSF_BASE + "/maps")
    txt = "".join(c for c in next_chunks(html) if isinstance(c, str))
    dec, out = json.JSONDecoder(), {}
    for m in re.finditer(r'\{"mapID":', txt):
        try:
            o, _ = dec.raw_decode(txt, m.start())
        except (ValueError, RecursionError):
            continue
        name = o.get("name") if isinstance(o, dict) else None
        if not okname(name):
            continue
        # The URL is built from the validated name; their `link` only says
        # whether an archive exists.
        link = o.get("link") == "/files/%s.zip" % name
        out.setdefault(name.lower(), {
            "name": name, "mode": "surf" if name.lower().startswith("surf_") else "bhop",
            "tier": o.get("tier") if type(o.get("tier")) is int else None,
            "url": "%s/files/%s.zip" % (KSF_BASE, name) if link else None,
            "src": "ksf"})
    if not KSF_MIN <= len(out) <= KSF_MAX:
        raise Refused("%d maps read out of ksf.surf/maps -- their page has "
                      "probably changed" % len(out))
    return out


def extra_list(path):
    """<state>/extra.tsv: `name sha1 url`, Momentum maps the public list does
    not carry.  A line that is not exactly that is dropped and counted."""
    out, bad = {}, 0
    try:
        fh = io.open(path, encoding="utf-8", errors="replace")
    except OSError:
        return out, bad
    with fh:
        for ln in fh:
            f = ln.split()
            if not f or f[0].startswith("#"):
                continue
            if (len(f) != 3 or not okname(f[0]) or not HEX40.fullmatch(f[1].lower())
                    or not okcdn(f[2])):
                bad += 1
                continue
            out.setdefault(f[0].lower(), {
                "name": f[0], "id": None, "sha": f[1].lower(), "url": f[2],
                "mode": "surf" if f[0].lower().startswith("surf_") else "bhop",
                "zh": None, "tier": None, "ranked": None, "src": "beta"})
    return out, bad


# --------------------------------------------------------------------------
# the library on disk

def inventory(maps_dir):
    """-> (lowercased name -> the on-disk stem; names held some other way).
    First spelling wins by sort order, surfd._scan_maps' rule, so both agree on
    which file a name means.  A `.BSP`, or an entry that is not a file, is in
    the second set: held, so never fetched over, and never opened."""
    inv, odd = {}, set()
    for f in sorted(os.listdir(maps_dir)):
        if not f.lower().endswith(".bsp") or f.startswith("."):
            continue
        if f.endswith(".bsp") and os.path.isfile(os.path.join(maps_dir, f)):
            inv.setdefault(f[:-4].lower(), f[:-4])
        else:
            odd.add(f[:-4].lower())
    return inv, odd - set(inv)


def stems(d, ext):
    """lowercased stem -> the spelling on disk, of the files in `d` ending `ext`."""
    try:
        return {f[:-len(ext)].lower(): f[:-len(ext)] for f in sorted(os.listdir(d), reverse=True)
                if f.endswith(ext) and not f.startswith(".")}
    except OSError:
        return {}


def file_sha1(path, cache):
    """SHA1 of `path`, cached by size and mtime (a stale cache is silent); None
    when the file cannot be read, which no published hash equals."""
    try:
        st = os.stat(path)
        key = [st.st_size, st.st_mtime_ns]
        hit = cache.get(os.path.basename(path))
        if isinstance(hit, list) and hit[:2] == key:
            return hit[2]
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            for blk in iter(lambda: fh.read(1 << 20), b""):
                h.update(blk)
    except OSError:
        return None
    cache[os.path.basename(path)] = key + [h.hexdigest()]
    cache["_dirty"] = cache.get("_dirty", 0) + 1
    # The first run hashes the whole library: a run killed in it keeps its work.
    if cache["_dirty"] >= 50:
        flush_hashes(cache)
    return h.hexdigest()


def flush_hashes(cache):
    if cache.get("_dirty") and cache.get("_path"):
        cache["_dirty"] = 0
        _save(cache["_path"], {k: v for k, v in cache.items() if not k.startswith("_")})


def publish(part, final, fresh):
    """Move a finished file into place, world-readable: importing surfd set
    umask 077, and nginx (www-data) serves these directories.  `fresh` means
    the name must still be free -- a file put there since the listing is kept,
    and False comes back."""
    os.chmod(part, 0o644)
    if not fresh:
        os.replace(part, final)
        return True
    try:
        os.link(part, final)            # fails if the name was taken meanwhile
    except FileExistsError:
        _rm(part)
        return False
    except OSError:                     # no hard links here: the check, then the move
        if os.path.exists(final):
            _rm(part)
            return False
        os.replace(part, final)
        return True
    _rm(part)
    return True


def write_file(path, raw, fresh=False):
    part = os.path.join(os.path.dirname(path), ".mapwatch.%s.part" % os.path.basename(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(part, "wb") as fh:
        fh.write(raw)
    return publish(part, path, fresh)


def sweep_leftovers(maps, state, site=""):
    """A killed run's .part files and archives: ours by name, and the lock is held."""
    for d in (maps, os.path.join(maps, "zones", "online"), os.path.join(maps, ".old"), site):
        try:
            for f in os.listdir(d):
                if f.startswith(".mapwatch.") and f.endswith(".part"):
                    _rm(os.path.join(d, f))
        except OSError:
            pass
    try:
        for f in os.listdir(os.path.join(state, "tmp")):
            _rm(os.path.join(state, "tmp", f))
    except OSError:
        pass


def zip_small(zp):
    """True when the archive's own end record claims at most MAX_ZIP_FILES
    entries in under 1 MB of directory.  Read BEFORE zipfile is: it loads the
    whole directory, and an archive can be all directory.  A zip64 archive is
    refused whole: zipfile takes its counts from the zip64 record instead, and
    no map needs one."""
    with open(zp, "rb") as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - 65557 - 76))
        tail = fh.read()
    at = tail.rfind(b"PK\x05\x06")
    if at < 0 or len(tail) - at < 22 or b"PK\x06\x07" in tail or b"PK\x06\x06" in tail:
        return False
    _disk, _cdisk, here, total, cdsize, off = struct.unpack("<4H2L", tail[at + 4:at + 20])
    return (here == total <= MAX_ZIP_FILES and cdsize <= 1 << 20
            and total != 0xFFFF and off != 0xFFFFFFFF)


def zip_bsp(zp, name, part, cap=MAX_MAP_BYTES):
    """Write the one .bsp of KSF archive `zp` to `part`.  -> ("ok", sha1, bytes)
    or (why, 0); `part` exists only after "ok".  Whatever zipfile raises on an
    archive it cannot read is "badzip": an encrypted member is a RuntimeError,
    an unknown method a NotImplementedError, a bad stream a zlib.error."""
    if not zip_small(zp):
        return ("badzip", 0)
    try:
        z = zipfile.ZipFile(zp)
    except Exception:
        return ("badzip", 0)
    with z:
        try:
            if len(z.infolist()) > MAX_ZIP_FILES:
                return ("badzip", 0)
            bsps = [i for i in z.infolist() if i.filename.lower().endswith(".bsp")]
        except Exception:
            return ("badzip", 0)
        if len(bsps) != 1:
            return ("bsps=%d" % len(bsps), 0)
        i = bsps[0]
        leaf = i.filename.replace("\\", "/").rsplit("/", 1)[-1]
        if leaf[:-4].lower() != name.lower():
            return ("wrongname", 0)
        if not 1024 <= i.file_size <= cap:
            return ("size", 0)
        # zipfile inflates in bounded pieces; for bzip2 and LZMA it decompresses
        # all it has read at once, whatever size the directory claims.
        if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            return ("method", 0)
        n, sha, why = 0, hashlib.sha1(), None
        try:
            dst = open(part, "wb")
        except OSError as e:
            raise LocalFault(e)
        with dst:
            try:
                with z.open(i) as src:
                    while why is None:
                        b = src.read(1 << 18)
                        if not b:
                            break
                        if not n and b[:4] != b"VBSP":
                            why = "notvbsp"
                        elif n + len(b) > cap:      # the header lied about the size
                            why = "size"
                        else:
                            n += len(b)
                            sha.update(b)
                            try:
                                dst.write(b)
                            except OSError as e:
                                raise LocalFault(e)
            except LocalFault:
                raise
            except Exception:
                why = "badzip"
        if why is None and n != i.file_size:
            why = "badzip"
        if why is not None:
            _rm(part)
            return (why, 0)
        return ("ok", sha.hexdigest(), n)


def zone_bytes(text, doc, want):
    """The zones of one /v1/maps/<id> reply as the bytes whose SHA1 is `want`, or
    None.  The slice of the reply itself first, then a compact re-dump: either
    is kept only on the hash."""
    cv = doc.get("currentVersion") if isinstance(doc, dict) else None
    zones = cv.get("zones") if isinstance(cv, dict) else None
    if not isinstance(zones, dict):
        return None
    dec = json.JSONDecoder()
    for m in re.finditer(r'"zones":', text):
        try:
            o, end = dec.raw_decode(text, m.end())
        except (ValueError, RecursionError):
            continue
        if o == zones:
            raw = text[m.end():end].encode("utf-8", "replace")
            if hashlib.sha1(raw).hexdigest() == want:
                return raw
            break
    for asc in (False, True):
        raw = json.dumps(zones, separators=(",", ":"),
                         ensure_ascii=asc).encode("utf-8", "replace")
        if hashlib.sha1(raw).hexdigest() == want:
            return raw
    return None


def zone_fetch(pacer, r):
    """The published zone bytes of approved map `r`, or None when the reply's
    zones are not the ones zoneHash names.  Raises Refused -- also for a reply
    with no zones in it at all, which is the host's and not this map's."""
    text = pacer.text("%s/maps/%d?expand=currentVersionWithZones" % (MOM_API, r["id"]))
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError):
        doc = None
    cv = doc.get("currentVersion") if isinstance(doc, dict) else None
    if not isinstance(cv, dict) or not isinstance(cv.get("zones"), dict):
        raise Refused("a reply with no zones in it")
    return zone_bytes(text, doc, r["zh"])


# --------------------------------------------------------------------------
# what the board knows

def wanted(now):
    """Maps somebody looked at within WANT_DAYS (surfd's mapwant), lowercased."""
    try:
        conn = S.connect()
        try:
            return {str(r[0]).lower() for r in conn.execute(
                "SELECT map FROM mapwant WHERE last >= ?", (now - WANT_DAYS * 86400,))}
        finally:
            conn.close()
    except Exception as e:      # an empty queue costs order, not the run
        print("  mapwant unreadable (%s): no map goes first" % e)
        return set()


def live_maps(now):
    """Maps the lobbies are on, lowercased.  None when that cannot be told, and
    an update waits: the table unreadable; EMPTY (a surfd that has heard nobody
    yet looks the same); or a lobby in it silent for two minutes -- it is down
    or surfd is not hearing it, and surfd drops such a row only after an hour
    (REAP_AFTER), in a heartbeat."""
    try:
        conn = S.connect()
        try:
            rows = conn.execute("SELECT map, last_seen FROM lobbies").fetchall()
        finally:
            conn.close()
    except Exception as e:
        print("  lobbies unreadable (%s): nothing held is changed this run" % e)
        return None
    if not rows or any((r[1] or 0) < now - 120 for r in rows):
        return None
    return {str(r[0]).lower() for r in rows}


def played():
    """Lowercased names of maps with a native run on the board, or a run, save,
    parked run or kept evidence on disk.  None when the board or the game's
    data folder cannot be read: a folder that is not THERE is no history, one
    that is listed and then cannot be opened is "cannot tell"."""
    try:
        conn = S.connect()
        try:
            out = {str(r[0]).lower() for r in conn.execute(
                "SELECT DISTINCT map FROM runs WHERE tier NOT IN (%s)"
                % ",".join("?" * len(S.TIERS_IMPORTED)), S.TIERS_IMPORTED)}
        finally:
            conn.close()
    except Exception as e:
        print("  runs unreadable (%s): no held map gets a first zone file this run" % e)
        return None
    data = os.path.dirname(os.path.normpath(S.RUNS_DIR))
    try:
        kinds = [d for d in ("runs", "resume", "saves", "evidence") if d in os.listdir(data)]
        for d in kinds:
            for n in os.listdir(os.path.join(data, d)):
                try:
                    if os.listdir(os.path.join(data, d, n)):    # an empty one is nothing
                        out.add(n.lower())
                except OSError:
                    out.add(n.lower())
    except OSError as e:
        print("  %s unreadable (%s): no map gets a first zone file this run" % (data, e))
        return None
    return out


# --------------------------------------------------------------------------

def be_small():
    """The box is the lobbies': a ceiling on this process, and the first to go
    if memory runs out anyway.  Linux only; elsewhere nothing."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEM, MAX_MEM))
    except (ImportError, ValueError, OSError):
        pass
    try:
        with open("/proc/self/oom_score_adj", "w") as fh:
            fh.write("800")
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", default=S.MAPS_DIR)
    ap.add_argument("--state", default=os.path.join(S.DATA_DIR, "mapwatch"))
    ap.add_argument("--site-zones", default="",
                    help="also copy a published zone file here when it holds "
                         "none of that name (what clients fetch)")
    ap.add_argument("--max", type=int, default=WATCH_MAX, help="downloads this run")
    ap.add_argument("--max-gb", type=float, default=WATCH_GB)
    ap.add_argument("--zones", type=int, default=ZONES_MAX, help="zone requests this run")
    ap.add_argument("--variants", type=int, default=0,
                    help="KSF archives of names Momentum also lists to compare "
                         "this run, kept as <name>%s where they differ" % VARIANT)
    ap.add_argument("--delay", type=float, default=API_DELAY)
    ap.add_argument("--updates", action="store_true",
                    help="replace a build or zone file that differs from the published one")
    ap.add_argument("--go", action="store_true", help="fetch; else a plan")
    a = ap.parse_args()

    lock = take_lock(a.state)
    if lock is None:
        print("another mapwatch holds %s -- not running beside it" % a.state)
        return 0
    # Every wait on a host has its clock; this is for whatever has none.  A
    # run that never ends holds the lock against every later one, so the
    # process is ended (the next run sweeps its .part).
    faulthandler.dump_traceback_later(RUN_SECONDS + FILE_SECONDS + 900, exit=True)
    be_small()
    try:
        return run(a)
    except (LocalFault, OSError) as e:
        print("this box could not read or write (%s): the run ends here" % e)
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()
        lock.close()


def run(a):
    now = int(time.time())
    deadline = now + RUN_SECONDS
    sp = os.path.join(a.state, "state.json")
    st = _load(sp)
    st = st if isinstance(st, dict) else {}
    later = st.setdefault("later", {})      # key -> [strikes, when, why]
    back = st.setdefault("back", {})        # key -> when its host last refused on it
    for k in [k for k, w in later.items() if now - w[1] > 2 * RETRY_DAYS * 86400]:
        del later[k]                        # the file left the lists long ago
    for k in [k for k, t in back.items() if now - t > RETRY_DAYS * 86400]:
        del back[k]
    hp = os.path.join(a.state, "hash.json")
    hashes = _load(hp)
    hashes = {k: v for k, v in hashes.items() if isinstance(v, list)} \
        if isinstance(hashes, dict) else {}
    hashes["_path"] = hp
    pacer = Pacer(a.delay)

    def waiting(key):
        w = later.get(key)
        return bool(w) and w[0] >= STRIKES and now - w[1] < RETRY_DAYS * 86400

    def again(key, why):
        w = later.get(key) or [0, 0, why]
        later[key] = [w[0] + 1, now, why]

    def skey(r):
        # With the hash: a new build of a shelved map is a new file.
        k = r["name"].lower()
        return "%s:ksf" % k if r["src"] == "ksf" else "%s:%s" % (k, r["sha"][:12])

    # Each source is read on its own: one refusing must not hide the others.
    mom, names, ksf, said, read = {}, set(), {}, [], set()
    try:
        mom, names = mom_list(pacer)
        read.add("mom")
    except Refused as e:
        said.append("momentum: NOT READ (%s)" % e)
    try:
        if ksf_parked(now):
            raise Refused(ksf_parked(now))
        with ksf_turn():
            ksf = ksf_list(pacer)
        read.add("ksf")
    except Refused as e:
        said.append("ksf: NOT READ (%s)" % e)
    extra, bad = extra_list(os.path.join(a.state, "extra.tsv"))
    # Which names are Momentum's decides whose build a new name gets, and
    # whether a Beta line is stale.  Unread, the last reading stands in; with
    # none, KSF's new maps and the Beta list wait.
    cp = os.path.join(a.state, "catalogue.json")
    if "mom" not in read:
        prev = _load(cp)
        prev = prev.get("momnames") if isinstance(prev, dict) else None
        if isinstance(prev, list):
            names = {str(n) for n in prev}
        else:
            if ksf or extra:
                said.append("no reading of Momentum's names, now or earlier: KSF's new "
                            "maps and the Beta list wait")
            ksf, extra = {}, {}
    for k in list(extra):
        if k in names:
            del extra[k]            # approved since the PC last listed it
    inv, odd = inventory(a.maps)
    held = set(inv) | odd
    print("lists: momentum %d approved, %d beta (%d bad line(s)), ksf %d; library %d"
          % (len(mom), len(extra), bad, len(ksf), len(held)))
    for s in said:
        print("  " + s)

    # NEW: a name the library does not hold.  Momentum's build of a name both
    # list goes under the plain name, as the PC's mount order has always had it.
    new = [mom[k] for k in sorted(mom) if k not in held]
    new += [extra[k] for k in sorted(extra) if k not in held]
    new += [ksf[k] for k in sorted(ksf)
            if k not in held and k not in names and k not in extra and ksf[k]["url"]]
    nolink = sum(1 for k in ksf if k not in held and k not in names and k not in extra
                 and not ksf[k]["url"])
    # DIFFERENT: held, and not the build Momentum publishes.
    diff, unread = [], 0
    for k in sorted(set(mom) | set(extra)):
        if k in inv:
            h = file_sha1(os.path.join(a.maps, inv[k] + ".bsp"), hashes)
            if h is None:
                unread += 1
            elif h != (mom.get(k) or extra[k])["sha"]:
                diff.append(mom.get(k) or extra[k])
    flush_hashes(hashes)
    print("new: %d (%d momentum, %d beta, %d ksf); held on another build: %d; "
          "ksf lists %d with no archive%s"
          % (len(new), sum(r["src"] == "mom" for r in new),
             sum(r["src"] == "beta" for r in new), sum(r["src"] == "ksf" for r in new),
             len(diff), nolink,
             "; %d held file(s) could not be read" % (unread + len(odd)) if unread or odd else ""))

    todo = new + ([r for r in diff if r["src"] == "mom"] if a.updates else [])
    todo = [r for r in todo if not waiting(skey(r))]
    todo.sort(key=lambda r: back.get(skey(r), 0))      # stable: a refused file goes last
    if not a.go:
        for r in todo[:max(0, a.max)]:
            print("   %-5s %-36s %s" % (r["src"], r["name"],
                                        "replace" if r["name"].lower() in inv else "new"))
        for r in ([] if a.updates else diff[:20]):
            print("   differs (left alone without --updates): %s" % r["name"])
        print("\nDRY RUN -- nothing fetched.  Pass --go.")
        return 0

    sweep_leftovers(a.maps, a.state, a.site_zones)
    os.makedirs(os.path.join(a.state, "tmp"), exist_ok=True)
    tally, took, fresh, back_again = {}, [], set(), []
    gets = {"n": 0, "bytes": 0}
    dead = {}                               # host -> why it is done for this run
    zdir = os.path.join(a.maps, "zones", "online")
    zidx = stems(zdir, ".json")
    verified, ztried = [], set()            # zone stems on the published hash; maps asked
    hist = {"at": 0.0, "names": None}

    def quiet(k):
        """True when the lobbies are heard and none is on `k`."""
        live = live_maps(int(time.time()))
        return live is not None and k not in live

    def unplayed(k, now=False):
        """True when the board and the disk were read and hold no run of `k`.
        Read again when a minute old, and `now` before a write: a first run
        can be set while this run downloads (the review's regression; the
        read is 0.6 s on the Pi).  A map installed this minute is not exempt:
        a name whose BSP was lost and comes back has its runs still."""
        if now or time.time() - hist["at"] > 60:
            hist["names"], hist["at"] = played(), time.time()
        return hist["names"] is not None and k not in hist["names"]

    def count(k, d=tally):
        d[k] = d.get(k, 0) + 1

    def refused(host, key, e):
        """A refusal while asking for `key`: the host is done for this run."""
        if own_fault(e.code):
            again(key, str(e))
        else:
            back[key] = now
        dead[host] = str(e)
        print("  %s refused (%s): nothing more is asked of it this run" % (host, e))

    def take(host, key, fetch):
        """One download under every budget.  -> its ("ok", sha1, bytes), or
        None when it was not made or left no file.  Whatever a reply makes
        Python raise that nothing here expected is that file's, and struck:
        left alone it would end every run at the same file."""
        if host in dead:
            return None
        if gets["n"] >= a.max or gets["bytes"] >= a.max_gb * 1e9 or time.time() > deadline:
            count("over this run's budget: next run")
            return None
        if shutil.disk_usage(a.maps).free / 1e9 < FLOOR_GB:
            dead["cdn"] = dead["ksf"] = "disk"
            print("under %d GB free: taking nothing more" % FLOOR_GB)
            return None
        if gets["n"]:
            time.sleep(GET_DELAY)
        gets["n"] += 1
        try:
            got = fetch()
        except Transient as e:
            # The link's or the host's, not the file's: no strike, and it goes
            # to the back so a file that always breaks cannot lead every run.
            back[key] = now
            count("cut short: another run")
            print("  %s: %s" % (key, e))
            return None
        except Refused as e:
            refused(host, key, e)
            return None
        except (LocalFault, OSError):
            raise
        except Exception as e:
            again(key, "error %s" % type(e).__name__)
            count("error")
            print("  %s: %s: %s" % (key, type(e).__name__, e))
            return None
        gets["bytes"] += got[-1]
        if got[0] != "ok":
            again(key, got[0])
            count(got[0])
            return None
        later.pop(key, None)
        back.pop(key, None)
        return got

    def ksf_get(url, leaf, member, part):
        zp = os.path.join(a.state, "tmp", leaf + ".zip")
        try:
            if ksf_parked(int(time.time())):    # the crawl was refused meanwhile
                raise Refused(ksf_parked(int(time.time())))
            with ksf_turn():
                got = download(url, zp, magic=b"PK")
            return zip_bsp(zp, member, part) if got[0] == "ok" else got
        finally:
            _rm(zp)

    def zone_ask(k, r, zkey):
        """-> the published bytes, or None; what went wrong is recorded here."""
        ztried.add(k)
        try:
            raw = zone_fetch(pacer, r)
        except Refused as e:
            if e.code == 404:
                again(zkey, "HTTP 404")
            else:
                refused("api", zkey, e)
            return None
        except Exception as e:          # see take()
            print("  %s: %s: %s" % (zkey, type(e).__name__, e))
            raw = None
        if raw is None:
            again(zkey, "zonehash")
        else:
            later.pop(zkey, None)
            back.pop(zkey, None)
        return raw

    def zone_put(k, raw, replace):
        """A FIRST zone file only while the name is free: one that arrived since
        the listing (mapsync copies them) is somebody's, and is kept."""
        zstem = zidx.get(k) or inv[k]       # never a second spelling of one name
        if not write_file(os.path.join(zdir, zstem + ".json"), raw, fresh=not replace):
            return False
        zidx[k] = zstem
        verified.append(zstem)
        return True

    for r in todo:
        key, name = r["name"].lower(), r["name"]
        host = "ksf" if r["src"] == "ksf" else "cdn"
        zkey = "z:%s:%s" % (key, (r.get("zh") or "")[:12])
        stem = inv.get(key)
        if stem is None and key in held:
            continue
        raw = None
        if stem is not None:
            if not a.updates or r["src"] != "mom" or key in fresh:
                continue
            # A build goes in WITH its zones or not at all, so they are had
            # first: they are small, and without them nothing is downloaded.
            if (not r["zh"] and key in zidx) or (r["zh"] and (waiting(zkey) or "api" in dead)):
                count("its zones cannot be had: build left")
                continue
            if not quiet(key):
                count("in play, or cannot tell: waits")
                continue
            if r["zh"]:
                raw = zone_ask(key, r, zkey)
                if raw is None:
                    count("its zones cannot be had: build left")
                    _save(sp, st)
                    continue
        part = os.path.join(a.maps, ".mapwatch.%s.part" % name)
        if host == "cdn":
            got = take(host, skey(r),
                       lambda: download(r["url"], part, r["sha"], magic=b"VBSP"))
        else:
            got = take(host, skey(r), lambda: ksf_get(r["url"], name, name, part))
        if not got:
            _save(sp, st)
            continue
        final = os.path.join(a.maps, (stem or name) + ".bsp")
        if stem is not None:
            if not quiet(key):          # again: the download took its time
                _rm(part)
                count("came into play meanwhile: waits")
                _save(sp, st)
                continue
            # Linked aside, not moved: the name is never without a file.
            old = file_sha1(final, hashes)
            if old is not None:
                keep = os.path.join(a.maps, ".old", "%s.%s.bsp" % (stem, old[:12]))
                os.makedirs(os.path.dirname(keep), exist_ok=True)
                if not os.path.exists(keep):
                    try:
                        os.link(final, keep)
                    except OSError:
                        tmp = os.path.join(a.maps, ".old", ".mapwatch.%s.part" % stem)
                        shutil.copy2(final, tmp)
                        os.replace(tmp, keep)
            publish(part, final, False)
            if raw is not None:
                zone_put(key, raw, True)
            count("replaced")
        elif publish(part, final, True):
            inv[key] = name
            held.add(key)
            fresh.add(key)
            count("installed")
            if not unplayed(key):
                back_again.append(name)
            # Its zones at once: it can be hosted from this second.  Not over a
            # zone file already here under that name (the zone loop reports
            # it), and under the same two looks as any first zone file.
            if (r["src"] == "mom" and r["zh"] and key not in zidx and "api" not in dead
                    and not waiting(zkey) and unplayed(key) and quiet(key)):
                raw = zone_ask(key, r, zkey)
                if raw is not None and quiet(key) and unplayed(key, True) and quiet(key):
                    zone_put(key, raw, False)
        else:
            count("the name was taken meanwhile: left")
            _save(sp, st)
            continue
        took.append(name)
        print("  %s %s %s %d bytes sha1 %s"
              % ("replaced" if stem is not None else "installed", r["src"], name,
                 got[2], got[1]))
        _save(sp, st)

    # A name both list holds Momentum's build, and KSF's times were set on
    # KSF's: its archive goes in beside it as <name>_css when the bytes differ.
    # `made` is the record that a _css file IS KSF's archive: sha1 by name.  A
    # _css file with no record (the state lost, or somebody's own file) is
    # compared with the archive like any other candidate, never written over.
    same, made = st.setdefault("same", {}), st.setdefault("made", {})
    foreign = st.setdefault("foreign", {})      # a _css file that was NOT the archive
    for kv in [kv for kv in made if kv not in inv
               or file_sha1(os.path.join(a.maps, inv[kv] + ".bsp"), hashes) != made[kv]]:
        del made[kv]
    if a.variants > 0 and "ksf" in read:
        prio = wanted(now)
        listed = set(ksf) | set(mom) | set(extra) | names
        cands = sorted((k for k in ksf
                        if ksf[k]["url"] and (k in names or k in extra) and k in inv
                        and k + VARIANT not in listed and k + VARIANT not in odd
                        and k + VARIANT not in made and okname(inv[k] + VARIANT)
                        and not waiting("v:" + k)),
                       key=lambda k: (back.get("v:" + k, 0), k not in prio, k))
        nv = 0
        for k in cands:
            plain = file_sha1(os.path.join(a.maps, inv[k] + ".bsp"), hashes)
            if plain is None or same.get(k) == plain:
                continue                # unreadable, or KSF's archive was this very build
            if k + VARIANT in inv and foreign.get(k) == file_sha1(
                    os.path.join(a.maps, inv[k + VARIANT] + ".bsp"), hashes):
                continue                # somebody's own, compared already: not asked again
            if nv >= a.variants:
                count("variants over --variants: next run")
                continue
            nv += 1
            name = inv[k] + VARIANT
            part = os.path.join(a.maps, ".mapwatch.%s.part" % name)
            got = take("ksf", "v:" + k,
                       lambda: ksf_get(ksf[k]["url"], inv[k], ksf[k]["name"], part))
            if not got:
                _save(sp, st)
                continue
            if got[1] == plain:
                _rm(part)
                same[k] = plain
                count("ksf's build is the one held")
            elif k + VARIANT in inv:
                # A file of that name was here already: KSF's only if it is.
                _rm(part)
                if file_sha1(os.path.join(a.maps, inv[k + VARIANT] + ".bsp"), hashes) == got[1]:
                    made[k + VARIANT] = got[1]
                    count("a %s file here is ksf's build" % VARIANT)
                else:
                    foreign[k] = file_sha1(os.path.join(a.maps, inv[k + VARIANT] + ".bsp"),
                                           hashes)
                    count("a %s file here is not ksf's build: left" % VARIANT)
            elif publish(part, os.path.join(a.maps, name + ".bsp"), True):
                inv[k + VARIANT] = name
                held.add(k + VARIANT)
                made[k + VARIANT] = got[1]
                count("ksf's build installed as %s" % VARIANT)
                print("  installed ksf %s %d bytes sha1 %s" % (name, got[2], got[1]))
            else:
                count("the name was taken meanwhile: left")
            _save(sp, st)

    # Zones for approved maps already held at the published build: absent, or
    # (with --updates) not the published file.
    zw, zasked, zdiff, zwait = {}, 0, 0, 0
    zidx.update(stems(zdir, ".json"))       # what arrived while the maps were coming
    for k in sorted(mom, key=lambda k: (back.get("z:%s:%s" % (k, (mom[k]["zh"] or "")[:12]), 0), k)):
        r = mom[k]
        if k not in inv or not r["zh"] or k in ztried:
            continue
        zkey = "z:%s:%s" % (k, r["zh"][:12])
        if file_sha1(os.path.join(a.maps, inv[k] + ".bsp"), hashes) != r["sha"]:
            continue
        if k in zidx:
            try:
                with open(os.path.join(zdir, zidx[k] + ".json"), "rb") as fh:
                    cur = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                continue
            if cur == r["zh"]:
                if zidx[k] not in verified:
                    verified.append(zidx[k])
                continue
        elif unplayed(k):
            cur = None                  # nobody has a run here: a first file changes nothing
        else:
            cur = ""                    # a first zone file under existing runs
        if cur is not None and not a.updates:
            zdiff += cur != ""
            zwait += cur == ""
            continue
        if waiting(zkey) or "api" in dead:
            continue
        # Any zone file changes what the map's next load times by: never while
        # a lobby is on it (a run in progress is in no list played() reads).
        if not quiet(k):
            count("in play, or cannot tell: waits", zw)
            continue
        if zasked >= a.zones or time.time() > deadline:
            count("over this run's budget: next run", zw)
            continue
        zasked += 1
        raw = zone_ask(k, r, zkey)
        if raw is None:
            count("not had", zw)
        elif not quiet(k) or (cur is None and not unplayed(k, True)) or not quiet(k):
            # Lobbies on both sides of the history read: one that came during
            # the request is seen before it can slip a run past that read.
            count("a run or a lobby came meanwhile: waits", zw)
        elif zone_put(k, raw, k in zidx):
            count("replaced" if cur else "written", zw)
        else:
            count("one arrived meanwhile: left", zw)
        _save(sp, st)
    # What clients fetch (cl_zonedl.qc): every published zone file held, where
    # the site has none of that name in any spelling.  Never over a file there.
    if a.site_zones and os.path.isdir(a.site_zones):
        site = stems(a.site_zones, ".json")
        for stem in verified:
            if stem.lower() not in site:
                with open(os.path.join(zdir, stem + ".json"), "rb") as fh:
                    if write_file(os.path.join(a.site_zones, stem + ".json"), fh.read(), True):
                        count("copied to the site", zw)
    flush_hashes(hashes)

    # What the lists said, for the tools that build the client's map list.
    cat = {}
    for src in (ksf, extra, mom):
        for k, r in src.items():
            c = cat.setdefault(k, {"name": r["name"], "mode": r["mode"], "src": ""})
            c["src"] += {"mom": "m", "beta": "b", "ksf": "k"}[r["src"]]
            c["ktier" if r["src"] == "ksf" else "mtier"] = r["tier"]
            if r["src"] != "ksf":
                c["sha"], c["ranked"] = r["sha"], r["ranked"]
    # KSF's build of a name both list: the files whose bytes were compared.
    for kv in made:
        k = kv[:-len(VARIANT)]
        if kv in inv and k in inv and k in ksf and kv not in ksf and kv not in names \
                and kv not in extra:
            cat[kv] = {"name": inv[kv], "mode": ksf[k]["mode"], "src": "k",
                       "ktier": ksf[k]["tier"], "of": inv[k]}
    if len(read) == 2:
        _save(cp, {"at": now, "maps": cat, "momnames": sorted(names)})
    st["last"] = {"at": now, "new": len(new), "differs": len(diff), "took": took}
    _save(sp, st)
    if back_again:
        print("  installed under a name that already has runs (their build may not be "
              "this one), or whose runs could not be read: %s" % ", ".join(sorted(back_again)))
    print("watch: %d request(s), %d download(s); maps: %s; zones: %s%s%s"
          % (pacer.made, gets["n"],
             ", ".join("%s %d" % kv for kv in sorted(tally.items())) or "nothing to take",
             ", ".join("%s %d" % kv for kv in sorted(zw.items())) or "nothing to write",
             "; %d zone file(s) differ from the published one and were left" % zdiff
             if zdiff else "",
             "; %d map(s) with runs have no zone file and were left one" % zwait
             if zwait else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
