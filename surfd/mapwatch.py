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
             <state>/betaids.tsv (P1093), `name sha1 id zoneHash`, gives a line
             of the same name and sha1 its map id: a separate file because a
             watcher older than P1093 reads any other extra.tsv line as bad.

WHAT IT INSTALLS: a map whose NAME the library does not hold.  A Momentum file
is kept only when its SHA1 is the one its row publishes -- the row and the hash
come from one API, so that proves the transfer, not the API.  A KSF archive is
kept only when it holds exactly one .bsp, named for the map, with a VBSP
header; nothing publishes a digest for it, so its build is `unknown`, as
maproster.py says of every CS:S map.  Both are written as .part, made
world-readable (importing surfd sets umask 077; nginx serves this directory)
and linked into place only while the name is still free.

ZONES ARE THE TIMING RULE, so they are written narrowly: Momentum's own, from
/v1/maps/<id>?expand=currentVersionWithZones, as the bytes that hash to
zoneHash (the file the game writes: surf_skyhaven, 7,407 bytes, the same SHA1)
-- or, where nothing in the reply hashes to it (92 maps on 12 Oct 2026:
Momentum saved their zones again, with a new dataTimestamp and globalRegions,
and left zoneHash behind), the reply's zones when they are THE ZONE FILE HELD,
SAVED AGAIN: the same `tracks`, key for key.  So nothing about where a run
starts, passes a stage or ends is taken on trust, only what the re-save put
outside them: globalRegions, which that day meant new allowBhop regions in
all 64 and no change to a cancel region (the one kind there that can end a
run).  That was 64 of the 92.  The other 28 (8 with a change inside
the tracks, 20 with no zone file here to compare) are Lex's word of 12 Oct,
"do both", and no rule: <state>/approved.json, which a person writes and this
only reads, gives each as its key (z:<map>:<12 of zoneHash>) and the SHA1 of
the very zones that were looked at, and only those bytes are taken for it.
In both cases the reply must be of the version the list named (id, bspHash,
zoneHash) and a file the game loads whole (zone_shaped: every number a JSON
number, read as the game reads it), and on the build itself every start, end
and stage lies inside the world and every restart point is a targetname or a
position there; a build that cannot be read is "could not be measured", and
nothing is written.  What is written is this parse of the zones written out again, never
the reply's own text: the file is the document that was checked.  Any other
map with no zone file held, or whose tracks have changed, is left and struck
(`zonetiming`): that needs its hash, or a person.  Zones taken this way are
recorded in state.json (`unhashed`, with the build they were measured on),
asked for again every UNHASHED_DAYS by a run with --updates, and replaced only
when more than the timestamp has changed.  A zone file this replaces is kept
in zones/online/.old/, as a replaced build is in maps/.old/.  All of it
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
own name, so its own download and its own native board (ROADMAP 8).  KSF's
archive and not a CS:S install's copy: on 11 Oct a PC's cstrike build was
KSF's on 3 of 6 maps.

ZONES GIVEN TO A SECOND BUILD (Lex, 11 Oct: "copy a momentum mod zones if the
map has a momentum mod version of the map").  A <name>_css that is KSF's
archive, or a port named <name>_<one of PORTS>, that Momentum does not list
itself and that has no zone file of its own takes the zone file this box
times <name> by, where <name> is held at the build Momentum publishes -- that
file whether or not it hashes to zoneHash: for 92 maps on 11 Oct Momentum's
own zones did not (re-saved in January with a new `globalRegions.allowBhop`,
the hash left as it was) -- when zonefit.py says the two builds share a
coordinate frame, the
target has every restart point the file names, and it carries no timer
triggers of its own.  Not otherwise: a zone is a world polygon, and 5 of the
71 pairs the PC tool measured in September were different maps sharing a
stem.  `given` in state.json records what was copied and onto which build: a
file somebody edited since is theirs, and one whose build has changed is
measured again and, if it no longer fits, moved aside (--updates) or reported.

THE MAP LIST (<state>/mapdl.txt, data/mapdl.txt's grammar): a row for every
surf/bhop map held, with a tenth column naming the map a second build is a
build OF.  surfd serves it to the game (/api/board?maps=1), so a new map is
offered without a release.

A BUILD OR A ZONE FILE THAT DIFFERS from the published one is REPORTED and left
alone without --updates: the runs on that map's board were set on what it
replaces, and nothing reads the old build back.  With it (approved maps, and a
Beta map whose own API reply names its betaids.tsv line's build) the old build is linked to <maps>/.old/<name>.<sha1
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
import math
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
import zonefit          # noqa: E402

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
# Suffixes that name ANOTHER COMPILE of a map, not another version of it: the
# ports among mapmeta.py's ALIAS_SUFFIXES.  `_v2`, `_new` and `_redux` are maps.
PORTS = ("ksf", "fix", "fixed", "go", "csgo", "njv", "mom")     # _css: only KSF's archive
NEW_DAYS = 14           # tools/mapscan.py's: how long a row wears the New badge
# Builds --updates leaves alone, by name.  None now: bhop_eazy was here (the
# engine gate compares `pm_dettest` on it between this box and Windows) until
# Lex had it moved to Momentum's build on both, 12 Oct.
KEEP_BUILD = ()
UNHASHED_DAYS = 7       # zones taken without their hash are asked for again this often
MAX_ZONE_BYTES = 256 << 10  # the largest zone file held is 60 KB
GAME_ZONES, GAME_POINTS = 256, 2048     # sh_zones.qc:102: past these it skips regions
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
    boards = set()
    lbs = m.get("leaderboards")
    for lb in lbs if isinstance(lbs, list) else []:
        if not isinstance(lb, dict):
            continue
        if (lb.get("gamemode") == gm and lb.get("trackType") == 0
                and lb.get("trackNum") == 1 and lb.get("style") == 0):
            tier = lb.get("tier") if type(lb.get("tier")) is int else None
            ranked = lb.get("type") == 0
        b = (lb.get("gamemode"), lb.get("trackType"), lb.get("trackNum"))
        if lb.get("style") == 0 and all(type(x) is int and 0 <= x < 1000 for x in b):
            boards.add(b)
    return {"name": name, "id": m["id"], "sha": sha, "url": url, "mode": mode,
            "zh": zh if HEX40.fullmatch(zh) else None, "tier": tier, "ranked": ranked,
            "src": "mom", "boards": sorted(boards)}


TRACKS_HEAD = "# map\tmapid\ttier\tgamemode\ttrackType\ttrackNum\n"
TRACKS_BOARDS_MAX = 512     # boards a map may claim; surf_kitsune has 81


def tracks_rows(mom, inv, old_lines):
    """P1117: momtracks.tsv (tools/msml.py's format) from this run's Momentum list,
    for momwatch/momfetch.  A map the list has and the library holds gets the
    list's boards; a map whose id, boards and tier the list agrees with, or that
    the list does not carry (Beta, other modes), keeps its lines byte for byte."""
    old = {}
    for ln in old_lines:
        f = ln.rstrip("\n").split("\t")
        if ln.startswith("#") or len(f) < 6:
            continue
        old.setdefault(f[0], []).append(ln if ln.endswith("\n") else ln + "\n")
    out = dict(old)
    for key, r in mom.items():
        if key not in inv or not r.get("boards") or len(r["boards"]) > TRACKS_BOARDS_MAX:
            continue
        lines = old.get(key, [])
        # P1117 review: a reply listing under half the map's own-gamemode boards
        # held is not trusted to drop the rest.
        gm = "1" if key.startswith("surf_") else "2"
        held = sum(1 for ln in lines if ln.split("\t")[3] == gm)
        if held and 2 * sum(1 for b in r["boards"] if str(b[0]) == gm) < held:
            continue
        f = lines[0].split("\t") if lines else []
        tier = r["tier"] if type(r.get("tier")) is int else (
            int(f[2]) if len(f) > 2 and f[2].isdigit() else 0)
        new = ["%s\t%d\t%d\t%d\t%d\t%d\n" % ((key, r["id"], tier) + tuple(b))
               for b in r["boards"]]
        if sorted(lines) != sorted(new):
            out[key] = new
    return [ln for k in sorted(out) for ln in out[k]]


def write_tracks(path, mom, inv):
    """-> (maps written, maps new or changed).  Atomic; untouched when unchanged."""
    try:
        with io.open(path, encoding="utf-8") as fh:
            old_lines = fh.readlines()
    except FileNotFoundError:
        old_lines = []
    rows = tracks_rows(mom, inv, old_lines)
    before, after = {}, {}
    for d, lines in ((before, old_lines), (after, rows)):
        for ln in lines:
            if not ln.startswith("#"):
                d.setdefault(ln.split("\t")[0], []).append(ln)
    changed = sum(1 for k, v in after.items() if before.get(k) != v)
    if changed:
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(TRACKS_HEAD + "".join(rows))
        os.replace(tmp, path)
    return len(after), changed


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


def extra_list(path, ids_path=None):
    """<state>/extra.tsv: `name sha1 url`, Momentum maps the public list does
    not carry.  A line that is not exactly that is dropped and counted.

    P1093: <state>/betaids.tsv, `name sha1 id zoneHash` (`-` = no zones), gives
    a line its map id and zoneHash when name and sha1 both match it.  Only a
    row with an id can have zones or replace a build, and only once the map's
    own API reply names that build (zone_fetch): the PC's cache can be stale."""
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
    try:
        fh = io.open(ids_path, encoding="utf-8", errors="replace") if ids_path else None
    except OSError:
        fh = None
    if fh is None:
        return out, bad
    with fh:
        for ln in fh:
            f = ln.split()
            if not f or f[0].startswith("#"):
                continue
            r = out.get(f[0].lower()) if len(f) == 4 else None
            if (r is None or r["name"] != f[0] or r["sha"] != f[1].lower()
                    or not re.fullmatch(r"[1-9][0-9]{0,8}", f[2])
                    or not (f[3] == "-" or HEX40.fullmatch(f[3].lower()))):
                continue            # no line of that name and build: nothing to give an id to
            r["id"] = int(f[2])
            r["zh"] = f[3].lower() if f[3] != "-" else None
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
    for d in (maps, os.path.join(maps, "zones", "online"), os.path.join(maps, ".old"),
              os.path.join(maps, "zones", "online", ".old"), site):
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


def zone_regions(zones):
    """-> [(tag, box, restart name, restart position, points)] of every region
    the game reads from `zones` -- the tracks', then globalRegions' as
    "g:<list>" -- or None where its reading and this one could part.  A number
    must be a JSON number: the game reads a string there with atof, which
    takes "9000_0e-9" for 9000 where float() makes 0.00009 of it."""
    def num(v):
        return type(v) in (int, float) and v == v and abs(v) < 1e7

    try:
        regs = list(zonefit.regions(zones))
        g = zones.get("globalRegions")
        if g is not None and not isinstance(g, dict):
            return None
        for name in ("cancel", "allowBhop", "overbounce"):      # sh_zones.qc:1429
            lst = (g or {}).get(name)
            if lst is None:
                continue
            if not isinstance(lst, list):
                return None
            regs += [("g:" + name, reg) for reg in lst]
    except (AttributeError, TypeError, ValueError, KeyError, IndexError, RecursionError):
        return None
    out = []
    for tag, reg in regs:
        if not isinstance(reg, dict):
            return None
        pts, b, h = reg.get("points"), reg.get("bottom", 0), reg.get("height", 0)
        if (not isinstance(pts, list) or len(pts) < 3 or not num(b) or not num(h)
                or not all(isinstance(p, list) and len(p) >= 2 and num(p[0]) and num(p[1])
                           for p in pts)):
            return None
        name, pos, yaw = (reg.get(k) for k in ("teleDestTargetname", "teleDestPos",
                                               "teleDestYaw"))
        # sh_zones.qc:1277: a position of three numbers wins over the name.
        if ((name is not None and not isinstance(name, str))
                or (yaw is not None and not num(yaw))
                or (pos is not None and not (isinstance(pos, list) and len(pos) >= 3
                                             and all(num(v) for v in pos[:3])))):
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append((tag, ((min(xs), min(ys), b), (max(xs), max(ys), b + h)), name or None,
                    tuple(pos[:3]) if pos else None, len(pts)))
    return out


def zone_shaped(zones):
    """Whether `zones` is a file the game loads whole and could time a map by:
    a start and an end on the main track; every region it reads a polygon of
    JSON numbers (zone_regions); no more regions or points than it loads.
    What a reply must be at least, where its hash cannot say what it is.  (Not
    "no cancel region over the start": 21 of the 985 zone files held have one
    whose box is.)"""
    regs = zone_regions(zones)
    if regs is None or len(regs) > GAME_ZONES or sum(r[4] for r in regs) > GAME_POINTS:
        return False
    return {r[0] for r in regs} >= {"main:start", "main:end"}


def zone_parts(raw):
    """-> (the tracks, everything but dataTimestamp) of a zone file's bytes, or
    None.  The first is what times a map; the second is the file but for the
    stamp a re-save moves."""
    try:
        z = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError, UnicodeDecodeError, AttributeError):
        return None
    if not isinstance(z, dict) or not isinstance(z.get("tracks"), dict):
        return None
    return z["tracks"], {k: v for k, v in z.items() if k != "dataTimestamp"}


def zone_on_build(raw, bsp):
    """Whether zones are `bsp`'s as far as the two files can show: every start,
    end and stage inside its world, every restart point of the tracks one of
    its targetnames or a position inside it (zonefit.fit's measures, on one
    build).  -> True, False, or None when the build cannot be read."""
    w = zonefit.world(bsp)
    if w is None:
        return None
    try:
        regs = zone_regions(json.loads(raw.decode("utf-8-sig")))
    except (ValueError, RecursionError, UnicodeDecodeError, AttributeError):
        return False
    if regs is None:
        return False

    def inside(lo, hi):
        return not any(hi[a] < w[0][a] - zonefit.SLACK or lo[a] > w[1][a] + zonefit.SLACK
                       for a in range(3))

    for tag, box, name, pos, _n in regs:
        if tag.startswith("g:"):
            continue
        if ((name and name not in w[2]) or (pos and not inside(pos, pos))
                or (tag.endswith(("start", "end", "stage")) and not inside(box[0], box[1]))):
            return False
    return True


def zone_bytes(text, doc, want):
    """-> (bytes, hashed) for the zones of one /v1/maps/<id> reply, or None.
    `hashed`: those bytes' SHA1 is `want` -- the slice of the reply itself
    first, then a compact re-dump.  Where neither is: this parse of them
    written out again (a repeated key, an escaped one or a NaN in the reply is
    then not in the file), when it is zone-shaped and of a zone file's size."""
    cv = doc.get("currentVersion") if isinstance(doc, dict) else None
    zones = cv.get("zones") if isinstance(cv, dict) else None
    if not isinstance(zones, dict):
        return None
    dec = json.JSONDecoder()
    sent = None
    for m in re.finditer(r'"zones":', text):
        try:
            o, end = dec.raw_decode(text, m.end())
        except (ValueError, RecursionError):
            continue
        if o == zones:
            sent = text[m.end():end].encode("utf-8", "replace")
            if hashlib.sha1(sent).hexdigest() == want:
                return sent, True
            break
    for asc in (False, True):
        raw = json.dumps(zones, separators=(",", ":"),
                         ensure_ascii=asc).encode("utf-8", "replace")
        if hashlib.sha1(raw).hexdigest() == want:
            return raw, True
    if not zone_shaped(zones):
        return None
    try:
        canon = json.dumps(zones, separators=(",", ":"), ensure_ascii=False,
                           allow_nan=False).encode("utf-8")
    except (ValueError, RecursionError, UnicodeEncodeError):
        return None
    return (canon, False) if len(canon) <= MAX_ZONE_BYTES else None


def zone_fetch(pacer, r):
    """-> (the zone bytes of approved map `r`, whether they hash to zoneHash,
    None), or (None, False, why) when the reply's zones are neither that nor
    fit to be taken without it.  Raises Refused -- also for a reply with no
    zones in it at all, which is the host's and not this map's."""
    text = pacer.text("%s/maps/%d?expand=currentVersionWithZones" % (MOM_API, r["id"]))
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError):
        doc = None
    cv = doc.get("currentVersion") if isinstance(doc, dict) else None
    # P1093: a Beta row is a line from a PC's cache, maybe days old.  Its zones
    # (and a build swap waiting on them) are taken only while the map's own
    # reply still names that build; otherwise the line is stale, not the map --
    # asked before the refusal below, which would end the API for the run.
    if (r["src"] == "beta" and isinstance(cv, dict)
            and (doc.get("id") != r["id"] or str(cv.get("bspHash")).lower() != r["sha"]
                 or not isinstance(cv.get("zones"), dict))):
        return None, False, "zoneversion"
    if not isinstance(cv, dict) or not isinstance(cv.get("zones"), dict):
        raise Refused("a reply with no zones in it")
    got = zone_bytes(text, doc, r["zh"])
    if got is None:
        return None, False, "zoneshape"
    # Without the hash, the reply must be of the version the list named.
    if not got[1] and (doc.get("id") != r["id"]
                       or str(cv.get("bspHash")).lower() != r["sha"]
                       or str(cv.get("zoneHash")).lower() != r["zh"]):
        return None, False, "zoneversion"
    return got[0], got[1], None


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


DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def held_extra_donors(extra, inv, zidx, zdir, maps_dir, hashes):
    out = set()
    for k, row in extra.items():
        if k not in inv or k not in zidx:
            continue
        bsp = os.path.join(maps_dir, inv[k] + ".bsp")
        if file_sha1(bsp, hashes) != row["sha"]:
            continue
        try:
            with open(os.path.join(zdir, zidx[k] + ".json"), "rb") as fh:
                raw = fh.read(MAX_ZONE_BYTES + 1)
            if len(raw) > MAX_ZONE_BYTES:
                continue
            doc = json.loads(raw.decode("utf-8-sig"))
            if zone_shaped(doc) and zone_on_build(raw, bsp) is True:
                out.add(zidx[k])
        except (OSError, ValueError, RecursionError, UnicodeDecodeError, OverflowError):
            print("  %s: held beta zones could not be checked: not a donor" % k)
    return out


def link_ports(cat, inv, momentum_names):
    """Related builds, not timer equivalence. Only real KSF roster names,
    one port suffix, and a held Momentum root. Never strip version suffixes.
    zonefit's independent geometry gate still decides whether zones transfer.
    """
    for name, row in cat.items():
        if name not in inv or name in momentum_names or row.get("of") or "k" not in row.get("src", ""):
            continue
        for suffix in PORTS:
            if not name.endswith("_" + suffix):
                continue
            base = name[:-len(suffix) - 1]
            if base in momentum_names and base in inv:
                row["of"], row["port"] = inv[base], True
            break
    # The display row can name KSF's independent rating even when KSF uses
    # only its suffixed name. Conflicting ratings are not collapsed into one.
    for base in momentum_names:
        ratings = {r.get("ktier") for r in cat.values()
                   if r.get("of", "").lower() == base and r.get("ktier")}
        if base in cat and not cat[base].get("ktier") and len(ratings) == 1:
            cat[base]["ktier"] = ratings.pop()


def list_rows(maps_dir, inv, cat, seen, today, cutoff):
    """The map list's lines: data/mapdl.txt's grammar, which the menu reads
    (ui_dl_load) and tools/mapscan.py also writes --
      dl <name> <mode> <src> <tier> <kb> <first-iso> <new> <mtier> <ktier> [<of>]
    One row per surf/bhop map HELD, named as the file is (the name is the
    download path).  `of` is the map a second build is a build of."""
    def tier(v):
        return v if type(v) is int and 1 <= v <= 10 else 0

    out = []
    for k in sorted(inv):
        stem = inv[k]
        if not okname(stem):            # surf_/bhop_, and a name a row can carry
            continue
        try:
            kb = (os.path.getsize(os.path.join(maps_dir, stem + ".bsp")) + 1023) // 1024
        except OSError:
            continue
        c = cat.get(k)
        c = c if isinstance(c, dict) else {}
        src = c.get("src") if isinstance(c.get("src"), str) else ""
        letters = ("k" if "k" in src else "") + ("m" if "m" in src or "b" in src else "")
        mt, kt = tier(c.get("mtier")), tier(c.get("ktier"))
        first = seen.get(k)
        if not (isinstance(first, list) and len(first) == 2 and first[1] in ("scan", "bootstrap")
                and isinstance(first[0], str) and DAY.fullmatch(first[0])):
            first = seen[k] = [today, "scan"]       # new, or a record of another shape
        row = "dl %s %s %s %d %d %s %d %d %d" % (
            stem, c.get("mode") if c.get("mode") in ("surf", "bhop") else k[:4],
            letters or "-", mt or kt, kb, first[0],
            1 if first[1] == "scan" and first[0] >= cutoff else 0, mt, kt)
        of = c.get("of")
        if isinstance(of, str) and of.lower() in inv and okname(inv[of.lower()]):
            row += " " + inv[of.lower()]
        out.append(row)
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
    ap.add_argument("--tracks", default=S.MOMTRACKS_PATH,
                    help="momtracks.tsv, rewritten from Momentum's list (P1117)")
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

    def table(key):
        """A table of state.json; one of another shape starts empty."""
        if not isinstance(st.get(key), dict):
            st[key] = {}
        return st[key]
    later = table("later")                  # key -> [strikes, when, why]
    back = table("back")                    # key -> when its host last refused on it
    for k in [k for k, w in later.items()
              if not (isinstance(w, list) and len(w) == 3 and type(w[0]) is int
                      and type(w[1]) in (int, float) and math.isfinite(w[1])
                      and isinstance(w[2], str))]:
        del later[k]
    for k in [k for k, t in back.items() if type(t) not in (int, float) or not math.isfinite(t)]:
        del back[k]
    for k in [k for k, w in later.items() if now - w[1] > 2 * RETRY_DAYS * 86400]:
        del later[k]                        # the file left the lists long ago
    for k in [k for k, t in back.items() if now - t > RETRY_DAYS * 86400]:
        del back[k]
    # A zone file struck for its hash alone is asked for again: 664 takes it.
    # A zone file struck for its hash alone, before 664, is asked for again.
    for k in [k for k, w in later.items() if k.startswith("z:") and w[2].startswith("zonehash")]:
        del later[k]
    # <state>/approved.json (the module docstring): zone key -> the SHA1 of the
    # zones a person approved for it.  Read here, never written.
    approved = _load(os.path.join(a.state, "approved.json"))
    approved = approved if isinstance(approved, dict) else {}
    # map -> {"zh", "b", "sha", "at"}: zones taken as sent, for that zoneHash, on that build
    unhashed = table("unhashed")
    unv = {}                    # maps whose zones came unhashed THIS run -> (zoneHash, build,
                                #   whether they are the file held but for its stamp)
    keeping = {}
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
    extra, bad = extra_list(os.path.join(a.state, "extra.tsv"),
                            os.path.join(a.state, "betaids.tsv"))
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

    # A Beta build is replaced only through its zones' request, which checks the
    # line against the map's own reply (zone_fetch): no id or zoneHash, no swap.
    # P1093: and not on a run whose list Momentum refused (that ends its host),
    # nor within a day of the reply naming another build than the line.
    stale_lines = table("stale")
    for k in [k for k, t in stale_lines.items() if not isinstance(t, (int, float)) or now - t > 86400]:
        del stale_lines[k]
    todo = new + ([r for r in diff if r["src"] == "mom"
                   or (r["src"] == "beta" and r["id"] and r["zh"] and "mom" in read
                       and skey(r) not in stale_lines)]
                  if a.updates else [])
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
        unv.pop(k, None)
        try:
            raw, hashed, why = zone_fetch(pacer, r)
        except Refused as e:
            if e.code == 404:
                again(zkey, "HTTP 404")
            elif r["src"] == "beta" and e.code in (401, 403):
                back[zkey] = now        # P1093: one Beta map refused, the API answers the rest
                stale_lines[skey(r)] = now
                print("  %s: refused (%s): this Beta map waits a day" % (zkey, e))
            else:
                refused("api", zkey, e)
            return None
        except Exception as e:          # see take()
            print("  %s: %s: %s" % (zkey, type(e).__name__, e))
            raw, hashed, why = None, False, "zoneshape"
        if raw is None and why == "zoneversion" and r["src"] == "beta":
            stale_lines[skey(r)] = now        # the line is behind the map: a day, until the PC rescans
        if raw is None and why == "zoneversion":
            # The list and this reply name different versions: the host's
            # moment, not this map's.  No strike; it goes to the back.
            back[zkey] = now
            print("  %s: the reply is of another version than the list named: another run" % zkey)
            return None
        if raw is None:
            again(zkey, why)
            return None
        if hashed:
            later.pop(zkey, None)
            back.pop(zkey, None)
            return raw
        # Without its hash, only as the zone file held, saved again (the
        # module docstring).  Its strikes stand until zone_fits has measured.
        try:
            with open(os.path.join(zdir, zidx[k] + ".json"), "rb") as fh:
                held = fh.read(MAX_ZONE_BYTES + 1)
        except (KeyError, OSError):
            held = None
        new, old = zone_parts(raw), zone_parts(held)
        if ((not new or not old or new[0] != old[0])
                and approved.get(zkey) != hashlib.sha1(raw).hexdigest()):
            again(zkey, "zonetiming")
            print("  %s: zones that do not hash to zoneHash, and %s: left"
                  % (zkey, "no zone file is held to compare them with" if held is None
                     else "they do not time the map as the file held does"))
            return None
        unv[k] = (r["zh"], r["sha"], bool(new and old and new[1] == old[1]))
        return raw

    def zone_fits(k, raw, bsp, zkey, d=tally):
        """Zones that came without their hash are measured on the build they
        are for before anything is written; what failed is recorded here."""
        if k not in unv:
            return True
        try:
            v = zone_on_build(raw, bsp)
        except Exception as e:          # see take(): one file must not end every run
            print("  %s: %s: %s" % (zkey, type(e).__name__, e))
            v = None
        if v:
            later.pop(zkey, None)
            back.pop(zkey, None)
            return True
        del unv[k]
        again(zkey, "zonebuild" if v is False else "zonemeasure")
        print("  %s: zones without their hash %s: left"
              % (zkey, "are not this build's" if v is False else "could not be measured on the build"))
        count("zones without their hash are not this build's: left" if v is False
              else "zones without their hash could not be measured on the build: left", d)
        return False

    def zsha(k):
        try:
            with open(os.path.join(zdir, zidx[k] + ".json"), "rb") as fh:
                return hashlib.sha1(fh.read()).hexdigest()
        except (OSError, KeyError):
            return None

    def can_keep():
        """Whether zones/online/.old can take a file.  Asked before anything
        is asked for that would replace a zone file held."""
        if "ok" not in keeping:
            p = os.path.join(zdir, ".old")
            keeping["ok"] = os.path.isdir(p) or not os.path.lexists(p)
            if not keeping["ok"]:
                print("  %s is not a folder: no zone file held is replaced this run" % p)
        return keeping["ok"]

    def zone_keep(path, stem, raw=None):
        """The zone file at `path` kept in .old under its hash, as a replaced
        build is: what timed a map is not thrown away.  -> False when it could
        not be kept, and then it is not replaced."""
        try:
            with open(path, "rb") as fh:
                had = fh.read()
        except FileNotFoundError:
            return True
        except OSError as e:
            print("  %s: the zone file held cannot be read (%s): left" % (stem, e))
            return False
        if had == raw:
            return True
        keep = os.path.join(zdir, ".old", "%s.%s.json" % (stem, hashlib.sha1(had).hexdigest()[:12]))
        try:
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            if not os.path.exists(keep):
                try:
                    os.link(path, keep)
                except OSError:
                    tmp = os.path.join(zdir, ".old", ".mapwatch.%s.part" % stem)
                    shutil.copy2(path, tmp)
                    os.replace(tmp, keep)
        except OSError as e:
            print("  %s: the zone file held could not be kept aside (%s): left" % (stem, e))
            return False
        return True

    def zone_put(k, raw, replace):
        """A FIRST zone file only while the name is free: one that arrived since
        the listing (mapsync copies them) is somebody's, and is kept.  One it
        replaces -- the file listed, or one that arrived since -- is kept
        aside first."""
        zstem = zidx.get(k) or inv[k]       # never a second spelling of one name
        old = zsha(k) if replace else None
        if replace and not zone_keep(os.path.join(zdir, zstem + ".json"), zstem, raw):
            return False
        if not write_file(os.path.join(zdir, zstem + ".json"), raw, fresh=not replace):
            return False
        zidx[k] = zstem
        verified.append(zstem)
        if k in unv:
            unhashed[k] = {"zh": unv[k][0], "b": unv[k][1],
                           "sha": hashlib.sha1(raw).hexdigest(), "at": now}
        else:
            unhashed.pop(k, None)
        # What clients fetch follows a file this replaced, where it WAS that
        # file: one that differs there is the shipped set's, and is kept.
        if old and a.site_zones and os.path.isdir(a.site_zones):
            sstem = stems(a.site_zones, ".json").get(k)
            try:
                if sstem:
                    with open(os.path.join(a.site_zones, sstem + ".json"), "rb") as fh:
                        same_there = hashlib.sha1(fh.read()).hexdigest() == old
                    if same_there:
                        write_file(os.path.join(a.site_zones, sstem + ".json"), raw)
            except OSError:
                pass
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
            if not a.updates or r["src"] not in ("mom", "beta") or key in fresh:
                continue
            if key in KEEP_BUILD:
                count("kept at the build held, by name (KEEP_BUILD)")
                continue
            # A build goes in WITH its zones or not at all, so they are had
            # first: they are small, and without them nothing is downloaded.
            if (not r["zh"] and key in zidx) or (r["zh"] and (waiting(zkey) or "api" in dead)):
                count("its zones cannot be had: build left")
                continue
            if not quiet(key):
                count("in play, or cannot tell: waits")
                continue
            if key in zidx and not can_keep():
                count("its zone file cannot be kept aside: build left")
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
            if raw is not None and not zone_fits(key, raw, part, zkey):
                _rm(part)
                count("its zones cannot be had: build left")
                _save(sp, st)
                continue
            if not quiet(key):          # again: the download took its time
                _rm(part)
                count("came into play meanwhile: waits")
                _save(sp, st)
                continue
            # Its zone file is kept aside BEFORE the build is swapped: a build
            # goes in with its zones or not at all.
            if (raw is not None and key in zidx
                    and not zone_keep(os.path.join(zdir, zidx[key] + ".json"), zidx[key], raw)):
                _rm(part)
                count("its zone file cannot be kept aside: build left")
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
            if (r["src"] in ("mom", "beta") and r["zh"] and r["id"] and key not in zidx and "api" not in dead
                    and (r["src"] == "mom" or "mom" in read)
                    and not waiting(zkey) and unplayed(key) and quiet(key)):
                raw = zone_ask(key, r, zkey)
                if (raw is not None and zone_fits(key, raw, final, zkey)
                        and quiet(key) and unplayed(key, True) and quiet(key)):
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
    same, made = table("same"), table("made")
    foreign = table("foreign")                  # a _css file that was NOT the archive
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

    # Zones for approved and Beta maps already held at the published build: absent, or
    # (with --updates) not the published file.
    zw, zasked, zdiff, zwait = {}, 0, 0, 0
    atbuild = set()                         # zone stems of maps held at the published build
    zidx.update(stems(zdir, ".json"))       # what arrived while the maps were coming
    # P1093: Beta maps too, by the id and zoneHash their extra.tsv line carries.
    zsrc = dict(mom)
    if "mom" in read:
        zsrc.update((k, r) for k, r in extra.items()
                    if r["id"] and r["zh"] and k not in zsrc and skey(r) not in stale_lines)
    for k in sorted(zsrc, key=lambda k: (back.get("z:%s:%s" % (k, (zsrc[k]["zh"] or "")[:12]), 0), k)):
        r = zsrc[k]
        if k not in inv or not r["zh"] or k in ztried:
            continue
        zkey = "z:%s:%s" % (k, r["zh"][:12])
        if file_sha1(os.path.join(a.maps, inv[k] + ".bsp"), hashes) != r["sha"]:
            continue
        if k in zidx:
            cur = zsha(k)
            if cur is None:
                continue
            if r["src"] == "mom":
                atbuild.add(zidx[k])    # Beta: held_extra_donors measures it on the build
            # The published file: by its hash, or -- taken without one -- as it
            # was last sent for this zoneHash and measured on this build, until
            # a run that may replace it is due to ask again.
            u = unhashed.get(k)
            known = (isinstance(u, dict) and u.get("zh") == r["zh"] and u.get("b") == r["sha"]
                     and u.get("sha") == cur)
            recent = (known and type(u.get("at")) in (int, float)
                      and 0 <= now - u["at"] < UNHASHED_DAYS * 86400)
            if cur == r["zh"] or recent or (known and not a.updates):
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
        if cur and not can_keep():
            count("the zone file held cannot be kept aside: left", zw)
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
        elif not zone_fits(k, raw, os.path.join(a.maps, inv[k] + ".bsp"), zkey, zw):
            pass
        elif cur and (hashlib.sha1(raw).hexdigest() == cur or (k in unv and unv[k][2])):
            # Asked again, and they are the zones held (but for the stamp a
            # re-save moves): nothing to write.
            if k in unv:
                unhashed[k] = {"zh": unv[k][0], "b": unv[k][1], "sha": cur, "at": now}
            if zidx[k] not in verified:
                verified.append(zidx[k])
            count("as last read", zw)
        elif not quiet(k) or (cur is None and not unplayed(k, True)) or not quiet(k):
            # Lobbies on both sides of the history read: one that came during
            # the request is seen before it can slip a run past that read.
            count("a run or a lobby came meanwhile: waits", zw)
        elif zone_put(k, raw, k in zidx):
            count("replaced" if cur else "written", zw)
        else:
            count("one arrived meanwhile: left", zw)
        _save(sp, st)
    # ZONES GIVEN TO A SECOND BUILD (the module docstring).  The donor is an
    # approved map, or checked extra, held at the published build, with the
    # zone file this box times it by; the target is not Momentum's own and has no zone
    # file anywhere the server reads.
    given, nofit = table("given"), table("nofit")
    local = stems(os.path.join(os.path.dirname(os.path.dirname(os.path.normpath(S.RUNS_DIR))),
                               "maps", "zones", "local"), ".json")
    donors = set(verified) | atbuild
    # Beta/extra maps have no API zoneHash. The owner's existing zones can
    # still seed a port when the BSP matches extra.tsv AND the zones fit that
    # donor build. Port geometry/restart names are checked independently below.
    donors |= held_extra_donors(extra, inv, zidx, zdir, a.maps, hashes)

    def donor_of(t):
        if t in made:
            return t[:-len(VARIANT)]
        for suf in PORTS:
            if t.endswith("_" + suf):
                return t[:-len(suf) - 1]
        return None

    for t in sorted(inv):
        d = donor_of(t)
        if (d is None or (d not in mom and d not in extra) or d not in inv or zidx.get(d) not in donors
                or t in names or t in extra or t in local):
            continue                    # `names`: Momentum's own map, usable row or not
        have = zsha(t) if t in zidx else None
        rec = given.get(t)
        rec = rec if isinstance(rec, dict) else {}
        if t in zidx and (have is None or have != rec.get("zh")):
            continue                    # its own zones, or ours since edited: somebody's
        dz = zsha(d)
        tsha = file_sha1(os.path.join(a.maps, inv[t] + ".bsp"), hashes)
        if dz is None or tsha is None:
            continue
        if dz == have and rec.get("t") == tsha:
            continue                    # the file given, on the build it was measured on
        # Given already, and the target's file is not the one that was measured.
        stale = have is not None and rec.get("t") != tsha
        nf = nofit.get(t)
        if isinstance(nf, list) and nf[:2] == [dz, tsha] and not stale:
            count("do not fit the build they would be given to", zw)
            continue
        if have is not None and not a.updates:
            if stale:
                count("given to a build that has since changed: left", zw)
            else:
                zdiff += 1
            continue
        with open(os.path.join(zdir, zidx[d] + ".json"), "rb") as fh:
            raw = fh.read()
        if hashlib.sha1(raw).hexdigest() != dz:
            continue                    # it changed under us: next run
        try:
            verdict, why = zonefit.fit(raw, os.path.join(a.maps, inv[d] + ".bsp"),
                                       os.path.join(a.maps, inv[t] + ".bsp"))
        except Exception as e:          # see take(): one file must not end every run
            verdict, why = None, "%s: %s" % (type(e).__name__, e)
        if verdict is None or verdict == "UNREADABLE":
            # NOT MEASURED is not "does not fit": nothing is given, and nothing
            # given is taken back.  What fit() raised is not remembered either.
            if verdict is not None:
                nofit[t] = [dz, tsha, verdict]
            count("could not be measured: left as they are", zw)
            print("  zones of %s and %s could not be measured (%s)" % (inv[d], inv[t], why))
            continue
        if verdict != "FIT":
            nofit[t] = [dz, tsha, verdict]
            count("do not fit the build they would be given to", zw)
            print("  zones of %s are not given to %s: %s (%s)" % (inv[d], inv[t], verdict, why))
            if stale:
                # What was given was measured on another build of the target.
                if quiet(t):
                    aside = os.path.join(zdir, ".old", "%s.%s.json" % (zidx[t], have[:12]))
                    os.makedirs(os.path.dirname(aside), exist_ok=True)
                    os.replace(os.path.join(zdir, zidx[t] + ".json"), aside)
                    # ...and the copy clients fetch, where it is that file.
                    sstem = stems(a.site_zones, ".json").get(t) if a.site_zones else None
                    try:
                        if sstem:
                            with open(os.path.join(a.site_zones, sstem + ".json"), "rb") as fh:
                                ours = hashlib.sha1(fh.read()).hexdigest() == have
                            if ours:
                                os.remove(os.path.join(a.site_zones, sstem + ".json"))
                    except OSError:
                        pass
                    del zidx[t]
                    del given[t]
                    count("taken back: the build they were given to has changed", zw)
                else:
                    count("given to a build that has since changed: left", zw)
                _save(sp, st)
            continue
        nofit.pop(t, None)
        if have is None and not a.updates and not unplayed(t):
            zwait += 1
            continue
        if not quiet(t) or (have is None and not a.updates and not unplayed(t, True)) \
                or not quiet(t):
            count("in play, or cannot tell: waits", zw)
            continue
        if zone_put(t, raw, have is not None):
            given[t] = {"of": inv[d], "zh": dz, "t": tsha}
            count("given to a second build of the map", zw)
            print("  zones of %s given to %s (%s)" % (inv[d], inv[t], why))
        else:
            count("one arrived meanwhile: left", zw)
        _save(sp, st)
    for t in [t for t in given if t not in inv]:
        del given[t]
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
    link_ports(cat, inv, names | set(extra))
    if "mom" in read:
        # P1117: momwatch/momfetch crawl only the boards this file names.
        n, changed = write_tracks(a.tracks, mom, inv)
        print("  momtracks: %d map(s), %d new or changed" % (n, changed))
    if len(read) == 2:
        _save(cp, {"at": now, "maps": cat, "momnames": sorted(names)})
    else:
        # One list unread: the last whole reading stands, plus what is new now.
        prev = _load(cp)
        prev = prev.get("maps") if isinstance(prev, dict) else None
        cat = dict(prev if isinstance(prev, dict) else {}, **{
            k: c for k, c in cat.items()
            if not isinstance(prev, dict) or k not in prev})
    # The list the game fetches.  The first run records every name as
    # `bootstrap`: New means it arrived after the list began (mapscan's rule).
    boot = not isinstance(st.get("seen"), dict)
    seen = table("seen")
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    if boot:
        seen.update({k: [today, "bootstrap"] for k in inv})
    rows = list_rows(a.maps, inv, cat, seen, today,
                     time.strftime("%Y-%m-%d", time.gmtime(now - NEW_DAYS * 86400)))
    for k in [k for k in seen if k not in inv]:
        del seen[k]
    tmp = os.path.join(a.state, "mapdl.txt.tmp")
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("FTESURF-MAPDL 1\n# written by surfd/mapwatch.py at %d -- do not edit\n"
                 "# dl <name> <mode> <src> <tier> <kb> <first-iso> <new> <mtier> <ktier> [<of>]\n"
                 % now)
        fh.write("".join(r + "\n" for r in rows))
    os.replace(tmp, os.path.join(a.state, "mapdl.txt"))
    st["last"] = {"at": now, "new": len(new), "differs": len(diff), "took": took,
                  "listed": len(rows)}
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
