"""reportd (P1391): player reports, a small service beside surfd.

F3 in the game posts a subject, text, client details and one JPEG to
POST /api/report. The owner reads, sorts and deletes them under /admin/reports,
signed in by surfd's own /admin session cookie (same secret, name and path).
Loopback gunicorn behind nginx (report.nginx, ftesurf-reportd.service).
Stdlib + Flask only: it imports no surfd module, so a surfd generation never
has to carry it.

Nothing a client sends is trusted: text is stored minus control, bidi and
zero-width characters and drawn only with textContent; screenshots are named by
row id. No address is stored: limits key on the network prefix (IPv4 /24, IPv6
/56) through `source`, 8 hex of an HMAC of the prefix that the panel shows so a
flood can be deleted in one click.
"""
import base64
import binascii
import glob
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import os
import re
import secrets
import sqlite3
import tempfile
import threading
import time
from contextlib import closing

from flask import Flask, jsonify, make_response, redirect, render_template, request, send_file, session
from flask.sessions import SecureCookieSessionInterface

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX = "/admin/reports"
MAX_REQUEST = 2 * 1024 * 1024     # report.nginx: client_max_body_size 2m
MAX_SUBJECT = 80
MAX_TEXT = 4000
MAX_META = 8 * 1024               # compact UTF-8 JSON after cleaning
MAX_SHOT = 1520435                # 1.45 MiB decoded: base64 + 8 KiB meta + text stays under 2m
MAX_BRACKETS = 2000               # '[' + '{' bytes: 2 MiB of nested [] costs ~100 MB in json.loads
PART_AGE = 600                    # a .part younger than this may be a live worker's (HUP)
ENV_RECHECK = 1                   # seconds between stats of SURFD_ENV
META_DEPTH = 3
CATEGORIES = ("perf", "render", "bug", "map", "feature", "other")
COPIED = ("player", "map", "server", "build")   # meta keys copied to sortable columns
COPIED_MAX = 128

# Read at call time so tests can lower them. All key on the source prefix.
# FLOOD_MAX counts every attempt in FLOOD_WINDOW, in process (one worker); the
# rest count STORED reports, so a restart does not reset them and a deleted
# report frees its slot.
FLOOD_MAX = 6
FLOOD_WINDOW = 60
FLOOD_TABLE_MAX = 4096
HOUR_MAX = 6
DAY_MAX = 20
GLOBAL_DAY_MAX = 300
STORE_MAX_ROWS = 5000
STORE_MAX_SHOT_BYTES = 1 << 30

LIMITED = "too many reports; try again later"
FULL = "report store full"
LIST_MAX = 200
DELETE_MAX = 200
SNIPPET = 160
TAG = re.compile(r"[0-9a-f]{8}")

# Copied from admin.py:122-123 and its logged_in() (admin.py:1364-1375): one
# cookie, two services, so they must expire it the same way.
SESSION_IDLE_MAX = 30 * 60
SESSION_ABS_MAX = 12 * 60 * 60
# admin.py:2192-2202 harden(); the page alone adds img-src 'self' for screenshots.
ADMIN_CSP = ("default-src 'none'; style-src 'self' 'unsafe-inline'; "
             "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
             "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
SHOT_CSP = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'"
ENV_KEYS = ("SURFD_ADMIN_SECRET", "SURFD_ADMIN_HASH", "SURFD_PROXIES")

SQL = """
CREATE TABLE IF NOT EXISTS reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 at REAL NOT NULL,
 source TEXT NOT NULL,
 subject TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT '',
 body TEXT NOT NULL DEFAULT '',
 meta TEXT NOT NULL DEFAULT '{}',
 player TEXT NOT NULL DEFAULT '',
 map TEXT NOT NULL DEFAULT '',
 server TEXT NOT NULL DEFAULT '',
 build TEXT NOT NULL DEFAULT '',
 shot TEXT NOT NULL DEFAULT '',
 shot_bytes INTEGER NOT NULL DEFAULT 0,
 seen INTEGER NOT NULL DEFAULT 0 CHECK(seen IN (0,1)));
CREATE INDEX IF NOT EXISTS reports_source_at ON reports (source, at);
CREATE INDEX IF NOT EXISTS reports_at ON reports (at);
CREATE TABLE IF NOT EXISTS report_totals (
 id INTEGER PRIMARY KEY CHECK(id=1), rows INTEGER NOT NULL, shot_bytes INTEGER NOT NULL);
INSERT OR IGNORE INTO report_totals VALUES (1, 0, 0);
CREATE TABLE IF NOT EXISTS report_schema (
 version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO report_schema(version) VALUES(1);
"""
COLUMNS = {"id", "at", "source", "subject", "category", "body", "meta", "player", "map",
           "server", "build", "shot", "shot_bytes", "seen"}
# AUTOINCREMENT so a deleted id is never handed out again: a delete unlinks
# <id>.jpg after its commit, and a reused id could lose the new report's file.

log = logging.getLogger("reportd")


# ---- configuration ---------------------------------------------------------

def read_env_file(path):
    """ENV_KEYS from a shell-sourceable KEY=VALUE file; {} if it cannot be read."""
    found = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name = name.strip()
                if name.startswith("export "):
                    name = name[len("export "):].strip()
                if name in ENV_KEYS:
                    found[name] = value.strip().strip("'\"")
    except (OSError, UnicodeError) as exc:
        log.warning("cannot read %s (%s); using the process environment", path, type(exc).__name__)
    return found


def parse_networks(text):
    nets = []
    for part in (text or "").split(","):
        if part.strip():
            try:
                nets.append(ipaddress.ip_network(part.strip(), strict=False))
            except ValueError:
                log.warning("SURFD_PROXIES entry %r is not a network; ignored", part.strip()[:64])
    return nets


def prefix_of(address):
    """IPv4 /24 or IPv6 /56 of an address string (IPv4-mapped counts as IPv4)."""
    ip = ipaddress.ip_address(address)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return str(ipaddress.ip_network("%s/%d" % (ip, 24 if ip.version == 4 else 56), strict=False))


def source_tag(key, prefix):
    return hmac.new(key, b"reportd-source\0" + prefix.encode("ascii"), hashlib.sha256).hexdigest()[:8]


def ensure_schema(db):
    """Versioned like inventory.ensure_event_schema: an unknown version refuses to start."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "report_schema" in tables:
        versions = [r[0] for r in db.execute("SELECT version FROM report_schema")]
        if not {"reports", "report_totals"} <= tables or versions != [1]:
            raise RuntimeError("Unsupported/incomplete report schema")
        if not COLUMNS <= {r[1] for r in db.execute("PRAGMA table_info(reports)")}:
            raise RuntimeError("Unsupported/incomplete report schema")
        return
    if tables & {"reports", "report_totals"}:
        raise RuntimeError("Unversioned report tables; preserve for inspection")
    try:
        db.executescript("BEGIN IMMEDIATE;\n" + SQL + "\nCOMMIT;")
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise


def reconcile(db):
    """Set report_totals from the rows (5000 at most): the cap reads only the total."""
    with db:
        db.execute("UPDATE report_totals SET rows = (SELECT COUNT(*) FROM reports),"
                   " shot_bytes = (SELECT COALESCE(SUM(shot_bytes), 0) FROM reports) WHERE id = 1")


# ---- the report itself -----------------------------------------------------

# C0 but \t and \n, DEL, C1, lone surrogates (json.loads accepts "\ud800"; sqlite
# cannot encode it), zero-width and bidi controls (with the Arabic letter mark), BOM.
_STRIP = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\ud800-\udfff"
                    "\u061c\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
_B64_SPACE = re.compile(r"[\r\n\t ]")


class Refused(ValueError):
    pass


class BadLength(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def clean(text):
    return _STRIP.sub("", text)


def _clean_meta(value, depth):
    if isinstance(value, str):
        return clean(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth < META_DEPTH and isinstance(value, list):
        return [_clean_meta(v, depth + 1) for v in value]
    if depth < META_DEPTH and isinstance(value, dict):
        return {clean(k): _clean_meta(v, depth + 1) for k, v in value.items()}
    raise Refused("meta nested too deep")


def _no_constant(name):
    raise Refused("bad JSON")


def _finite(text):
    value = float(text)
    if not math.isfinite(value):        # 1e400: stored as Infinity, the page's JSON.parse fails
        raise Refused("bad JSON")
    return value


def parse(raw):
    """The request body -> cleaned fields. Raises Refused with the 400 reason."""
    if raw.count(b"[") + raw.count(b"{") > MAX_BRACKETS:
        raise Refused("too complex")
    # Invalid UTF-8 is replaced rather than refused: a Quake name with raw high
    # bytes in meta should not cost the whole report.
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    try:
        doc = json.loads(text, parse_constant=_no_constant, parse_float=_finite)
    except (ValueError, RecursionError):
        raise Refused("bad JSON")
    if not isinstance(doc, dict):
        raise Refused("bad JSON")
    if doc.get("v") != 1 or isinstance(doc.get("v"), bool):
        raise Refused("unsupported version")

    subject = doc.get("subject")
    if not isinstance(subject, str):
        raise Refused("subject required")
    subject = clean(subject).strip()
    if not 1 <= len(subject) <= MAX_SUBJECT:
        raise Refused("subject must be 1-%d characters" % MAX_SUBJECT)

    category = doc.get("category", "")
    if not isinstance(category, str) or (category and category not in CATEGORIES):
        raise Refused("bad category")

    body = doc.get("body", "")
    if not isinstance(body, str):
        raise Refused("bad body")
    body = clean(body)
    if len(body) > MAX_TEXT:
        raise Refused("text must be at most %d characters" % MAX_TEXT)

    meta = doc.get("meta", {})
    if not isinstance(meta, dict):
        raise Refused("meta must be an object")
    meta = _clean_meta(meta, 0)
    meta_text = json.dumps(meta, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(meta_text.encode("utf-8")) > MAX_META:
        raise Refused("meta too large")

    shot = doc.get("shot", "")
    if not isinstance(shot, str):
        raise Refused("bad screenshot")
    shot = _B64_SPACE.sub("", shot)
    if len(shot) > 4 * ((MAX_SHOT + 2) // 3):
        raise Refused("screenshot too large")
    try:
        jpeg = base64.b64decode(shot, validate=True) if shot else b""
    except (binascii.Error, ValueError):
        raise Refused("screenshot is not base64")
    if len(jpeg) > MAX_SHOT:
        raise Refused("screenshot too large")
    if jpeg and not (jpeg[:3] == b"\xff\xd8\xff" and jpeg[-2:] == b"\xff\xd9"):
        raise Refused("screenshot is not a JPEG")

    out = {"subject": subject, "category": category, "body": body,
           "meta": meta_text, "shot": jpeg}
    for key in COPIED:
        value = meta.get(key)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            value = ""
        out[key] = str(value).strip()[:COPIED_MAX]
    return out


def read_body(limit):
    """Exactly Content-Length bytes, at most `limit`. Chunked bodies get 411
    (hidupload.py's rule): Werkzeug 2.2 under gunicorn would read one whole."""
    total = request.content_length
    if total is None:
        raise BadLength(411, "length required")
    if total > limit:
        raise BadLength(413, "request too large")
    stream, chunks, remaining = request.stream, [], total
    while remaining:
        chunk = stream.read(min(65536, remaining))
        if not chunk:
            raise BadLength(400, "body truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def over_limit(conn, tag, now):
    """LIMITED or None: the per-prefix hour/day caps and the global day cap."""
    def count(where, *args):
        return conn.execute("SELECT COUNT(*) FROM reports WHERE " + where, args).fetchone()[0]
    if (count("source = ? AND at > ?", tag, now - 3600) >= HOUR_MAX
            or count("source = ? AND at > ?", tag, now - 86400) >= DAY_MAX
            or count("at > ?", now - 86400) >= GLOBAL_DAY_MAX):
        return LIMITED
    return None


def store(conn, directory, tag, now, fields):
    """(id, None) once committed, or (None, (status, message)). The limits are
    checked again under the write lock; only then is the JPEG written, to a
    temp name renamed to <id>.jpg inside the transaction. On any failure
    neither the row nor the file survives."""
    jpeg = fields["shot"]
    temp = final = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        if over_limit(conn, tag, now):
            conn.rollback()
            return None, (429, LIMITED)
        rows, stored = conn.execute(
            "SELECT rows, shot_bytes FROM report_totals WHERE id = 1").fetchone()
        if rows >= STORE_MAX_ROWS or stored + len(jpeg) > STORE_MAX_SHOT_BYTES:
            conn.rollback()
            return None, (503, FULL)
        rid = conn.execute(
            "INSERT INTO reports (at, source, subject, category, body, meta, player, map,"
            " server, build, shot_bytes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (now, tag, fields["subject"], fields["category"], fields["body"],
             fields["meta"], fields["player"], fields["map"], fields["server"],
             fields["build"], len(jpeg))).lastrowid
        conn.execute("UPDATE report_totals SET rows = rows + 1, shot_bytes = shot_bytes + ?"
                     " WHERE id = 1", (len(jpeg),))
        if jpeg:
            fd, temp = tempfile.mkstemp(prefix=".shot-", suffix=".part", dir=directory)
            with os.fdopen(fd, "wb") as out:
                out.write(jpeg)
                out.flush()
                os.fsync(out.fileno())
            name = "%d.jpg" % rid
            final = os.path.join(directory, name)
            os.replace(temp, final)
            temp = None
            conn.execute("UPDATE reports SET shot = ? WHERE id = ?", (name, rid))
        conn.commit()
        final = None
        return rid, None
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        for path in (temp, final):
            if path:
                try:
                    os.unlink(path)
                except OSError as exc:
                    log.error("could not remove %s (%s)", path, type(exc).__name__)


# ---- admin reads and the deletes -------------------------------------------

SORTS = {"at": "at", "subject": "subject COLLATE NOCASE", "category": "category",
         "map": "map COLLATE NOCASE", "player": "player COLLATE NOCASE",
         "server": "server COLLATE NOCASE", "build": "build COLLATE NOCASE",
         "source": "source"}


def _int(text, default, low, high):
    if text in (None, ""):
        return default
    if not re.fullmatch(r"[0-9]{1,9}", text):
        raise ValueError("bad number")
    value = int(text)
    if not low <= value <= high:
        raise ValueError("number out of range")
    return value


def listing(conn, args):
    """Rows without the full body, the filtered total and per-category counts.
    `args` is the query string; ValueError means 400."""
    sort = args.get("sort") or "at"
    direction = (args.get("dir") or ("desc" if sort == "at" else "asc")).lower()
    category = args.get("category") or ""
    source = args.get("source") or ""
    q = (args.get("q") or "").strip()
    if sort not in SORTS or direction not in ("asc", "desc"):
        raise ValueError("bad sort")
    if category not in CATEGORIES + ("", "none"):
        raise ValueError("bad category")
    if source and not TAG.fullmatch(source):
        raise ValueError("bad source")
    if len(q) > 100:
        raise ValueError("search too long")
    offset = _int(args.get("offset"), 0, 0, 10 ** 9)
    limit = _int(args.get("limit"), 50, 1, LIST_MAX)

    where, params = [], []
    if category:
        where.append("category = ?")
        params.append("" if category == "none" else category)
    if source:
        where.append("source = ?")
        params.append(source)
    if q:
        like = "%" + re.sub(r"([\\%_])", r"\\\1", q) + "%"
        where.append("(" + " OR ".join("%s LIKE ? ESCAPE '\\'" % c
                                       for c in ("subject", "body", "player", "map")) + ")")
        params += [like] * 4
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute("SELECT COUNT(*) FROM reports" + clause, params).fetchone()[0]
    rows = conn.execute(
        "SELECT id, at, source, subject, category, substr(body, 1, %d) AS snippet,"
        " length(body) AS body_len, player, map, server, build,"
        " shot <> '' AS has_shot, shot_bytes, seen FROM reports%s"
        " ORDER BY %s %s, id %s LIMIT ? OFFSET ?"
        % (SNIPPET, clause, SORTS[sort], direction, direction),
        params + [limit, offset]).fetchall()
    counts = {"all": 0, "unseen": 0}
    for cat, n, unseen in conn.execute(
            "SELECT category, COUNT(*), SUM(seen = 0) FROM reports GROUP BY category"):
        counts[cat or "none"] = n
        counts["all"] += n
        counts["unseen"] += unseen
    return {"ok": True, "rows": [dict(r) for r in rows], "total": total,
            "counts": counts, "sort": sort, "dir": direction,
            "offset": offset, "limit": limit}


def detail(conn, rid):
    """The full row with meta parsed, marking it seen; None if there is none."""
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (rid,)).fetchone()
    if row is None:
        return None
    if not row["seen"]:
        with conn:
            conn.execute("UPDATE reports SET seen = 1 WHERE id = ?", (rid,))
    out = {k: row[k] for k in row.keys() if k not in ("meta", "shot")}
    out["seen"] = 1
    out["was_seen"] = row["seen"]
    out["has_shot"] = bool(row["shot"])
    out["from_source"] = conn.execute("SELECT COUNT(*) FROM reports WHERE source = ?",
                                      (row["source"],)).fetchone()[0]
    try:
        out["meta"] = json.loads(row["meta"])
    except ValueError:
        out["meta"] = {}
    return out


def parse_ids(text):
    parts = [p.strip() for p in (text or "").split(",") if p.strip()]
    if not parts or len(parts) > DELETE_MAX or not all(re.fullmatch(r"[0-9]{1,12}", p) for p in parts):
        raise ValueError("ids must be 1-%d report numbers, comma separated" % DELETE_MAX)
    return sorted({int(p) for p in parts})


def delete(conn, directory, where, args):
    """Rows matching `where` go in one transaction with the totals; their files
    after the commit (a missing one is fine)."""
    try:
        conn.execute("BEGIN IMMEDIATE")
        found = conn.execute("SELECT id, shot <> '', shot_bytes FROM reports WHERE " + where,
                             args).fetchall()
        conn.execute("DELETE FROM reports WHERE " + where, args)
        conn.execute("UPDATE report_totals SET rows = rows - ?, shot_bytes = shot_bytes - ?"
                     " WHERE id = 1", (len(found), sum(r[2] for r in found)))
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    for rid, has_shot, _ in found:
        if not has_shot:
            continue
        try:
            os.unlink(os.path.join(directory, "%d.jpg" % rid))
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.error("report %d: screenshot not removed (%s)", rid, type(exc).__name__)
    return len(found)


# ---- the app ---------------------------------------------------------------

def create_app(state=None, env_file=None, clock=time.time, environ=None):
    environ = os.environ if environ is None else environ
    state = state or environ.get("REPORTD_STATE")
    if not state:
        raise RuntimeError("REPORTD_STATE is not set")
    env_file = env_file or environ.get("SURFD_ENV", "/srv/nvme/surfd/surfd.env")
    db_path = os.path.join(state, "reports.sqlite3")
    shots = os.path.join(state, "shots")
    os.makedirs(shots, exist_ok=True)
    for stale in glob.glob(os.path.join(shots, ".shot-*.part")):
        try:
            if clock() - os.stat(stale).st_mtime > PART_AGE:
                os.unlink(stale)
        except OSError as exc:
            log.error("stale %s not removed (%s)", stale, type(exc).__name__)
    with closing(sqlite3.connect(db_path, timeout=5.0)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        ensure_schema(db)
        reconcile(db)
    insecure = environ.get("SURFD_ADMIN_INSECURE_COOKIE", "0") in ("1", "true")
    source = environ.get("REPORTD_SOURCE", "")
    source = source if re.fullmatch(r"[0-9A-Za-z._-]{1,64}", source) else "unset"

    app = Flask(__name__, template_folder=os.path.join(HERE, "templates"), static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST
    # surfd's cookie contract, admin.py's build_blueprint: one session, two services.
    app.config.update(SESSION_COOKIE_NAME="surfd_admin", SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=not insecure,
                      SESSION_COOKIE_PATH="/admin")
    cfg, cfg_lock = {"stat": None, "checked": None}, threading.Lock()

    def env_stat():
        try:
            st = os.stat(env_file)
            return st.st_mtime_ns, st.st_size, st.st_ino
        except OSError:
            return None

    def configure(stat):
        filed = read_env_file(env_file)

        def setting(name, default=None):
            return filed.get(name) or environ.get(name) or default

        secret = setting("SURFD_ADMIN_SECRET") or ""
        admin_on = bool(setting("SURFD_ADMIN_HASH")) and len(secret) >= 32
        cfg.update(stat=stat, admin_on=admin_on,
                   proxies=parse_networks(setting("SURFD_PROXIES", "127.0.0.1/32,::1/128")),
                   tag_key=secret.encode("utf-8") if len(secret) >= 32 else _state_key(state))
        app.secret_key = secret if admin_on else None

    def refresh():
        """Re-read SURFD_ENV when it changes, so a rotated secret (mkadminpw.py)
        retires old cookies here too; stat'ed at most every ENV_RECHECK s."""
        with cfg_lock:
            now = clock()
            if cfg["checked"] is not None and 0 <= now - cfg["checked"] < ENV_RECHECK:
                return
            cfg["checked"] = now
            stat = env_stat()
            if stat != cfg["stat"]:
                configure(stat)
                log.info("%s read: admin %s", env_file, "on" if cfg["admin_on"] else "OFF")

    class Sessions(SecureCookieSessionInterface):
        # Before the cookie is read, not in before_request (which runs after
        # it): the request that notices a new secret already uses it.
        def open_session(self, app_, req):
            refresh()
            return super().open_session(app_, req)

    app.session_interface = Sessions()
    configure(env_stat())
    flood, flood_lock = {}, threading.Lock()
    log.info("reportd source %s, state %s, admin %s%s", source, state,
             "on" if cfg["admin_on"] else "OFF (no SURFD_ADMIN_HASH, or SURFD_ADMIN_SECRET under 32)",
             ", cookie insecure" if cfg["admin_on"] and insecure else "")

    def connect():
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def fail(code, message):
        resp = jsonify({"ok": False, "error": message})
        resp.status_code = code
        return resp

    def client_ip():
        """X-Real-IP only from our own proxy (SURFD_PROXIES, loopback by default)."""
        peer = request.remote_addr or "0.0.0.0"
        try:
            trusted = any(ipaddress.ip_address(peer) in n for n in cfg["proxies"])
        except ValueError:
            trusted = False
        claimed = (request.headers.get("X-Real-IP") or "").strip()
        if trusted and claimed:
            try:
                return str(ipaddress.ip_address(claimed))
            except ValueError:
                pass
        return peer

    def flood_ok(tag, now):
        with flood_lock:
            if len(flood) > FLOOD_TABLE_MAX:
                for k in [k for k, v in flood.items() if not v or v[-1] <= now - FLOOD_WINDOW]:
                    del flood[k]
                if len(flood) > FLOOD_TABLE_MAX:
                    flood.clear()
            hits = [t for t in flood.get(tag, ()) if t > now - FLOOD_WINDOW]
            ok = len(hits) < FLOOD_MAX
            if ok:
                hits.append(now)
            flood[tag] = hits
            return ok

    @app.post("/api/report")
    def report_post():
        now = float(clock())
        try:
            tag = source_tag(cfg["tag_key"], prefix_of(client_ip()))
        except ValueError:
            return fail(400, "no client address")
        # Everything that needs only the address comes before the body is read.
        if not flood_ok(tag, now):
            return fail(429, LIMITED)
        try:
            with closing(connect()) as conn:
                limited = over_limit(conn, tag, now)
        except sqlite3.Error as exc:
            log.error("limit read failed: %s", exc)
            return fail(500, "storage error")
        if limited:
            return fail(429, limited)
        if request.mimetype != "application/json":
            return fail(400, "content type must be application/json")
        try:
            fields = parse(read_body(MAX_REQUEST))
        except BadLength as exc:
            return fail(exc.status, str(exc))
        except Refused as exc:
            return fail(400, str(exc))
        try:
            with closing(connect()) as conn:
                rid, refused = store(conn, shots, tag, now, fields)
        except (sqlite3.Error, OSError) as exc:
            log.error("report store failed: %s", exc)
            return fail(500, "storage error")
        if refused:
            return fail(*refused)
        log.info("report %d stored (source %s, %s, %d text chars, %d byte shot)", rid, tag,
                 fields["category"] or "-", len(fields["body"]), len(fields["shot"]))
        return jsonify({"ok": True, "id": rid})

    # ---- admin: surfd's session, admin.py's rules ----

    def logged_in():
        if not cfg["admin_on"] or not session.get("ok"):
            return False
        now = clock()
        if now - session.get("seen", 0) > SESSION_IDLE_MAX:
            session.clear()
            return False
        if now - session.get("born", 0) > SESSION_ABS_MAX:
            session.clear()
            return False
        session["seen"] = now
        return True

    def csrf_token():
        tok = session.get("csrf")
        if not tok:
            tok = secrets.token_urlsafe(32)
            session["csrf"] = tok
        return tok

    def control(fn):
        """admin.py's control(): a session, same-origin, and the session's CSRF token."""
        def wrapper(*a, **kw):
            if not logged_in():
                return fail(401, "not logged in")
            site = request.headers.get("Sec-Fetch-Site")
            if site is not None and site != "same-origin":
                log.warning("%s refused, Sec-Fetch-Site %r", request.path, site[:32])
                return fail(403, "cross-origin request refused")
            sent, held = request.form.get("csrf", ""), session.get("csrf", "")
            if not held or not sent or not hmac.compare_digest(sent, held):
                return fail(400, "stale form -- reload the page and try again")
            return fn(*a, **kw)
        wrapper.__name__ = fn.__name__
        return wrapper

    def removed(where, args, what, newer=None):
        """Delete; `newer` (where, args) counts what a source delete left alone."""
        try:
            with closing(connect()) as conn:
                gone = delete(conn, shots, where, args)
                kept = conn.execute("SELECT COUNT(*) FROM reports WHERE " + newer[0],
                                    newer[1]).fetchone()[0] if newer else 0
        except sqlite3.Error as exc:
            log.error("delete failed: %s", exc)
            return fail(500, "storage error")
        log.info("deleted %d report(s) (%s)", gone, what)
        message = "deleted %d" % gone
        if kept:
            message += " (%d newer from this source kept)" % kept
        return jsonify({"ok": True, "message": message})

    @app.get(PREFIX)
    def page():
        if not logged_in():
            return redirect("/admin/login")
        resp = make_response(render_template("reportd_reports.html", csrf=csrf_token(),
                                             categories=list(CATEGORIES)))
        resp.headers["Content-Security-Policy"] = ADMIN_CSP + "; img-src 'self'"
        return resp

    @app.get(PREFIX + "/api/list")
    def api_list():
        if not logged_in():
            return fail(401, "not logged in")
        try:
            with closing(connect()) as conn:
                return jsonify(listing(conn, request.args))
        except ValueError as exc:
            return fail(400, str(exc))
        except sqlite3.Error as exc:
            log.error("list failed: %s", exc)
            return fail(500, "storage error")

    @app.get(PREFIX + "/api/item/<int:rid>")
    def api_item(rid):
        if not logged_in():
            return fail(401, "not logged in")
        try:
            with closing(connect()) as conn:
                row = detail(conn, rid)
        except sqlite3.Error as exc:
            log.error("report %d read failed: %s", rid, exc)
            return fail(500, "storage error")
        if row is None:
            return fail(404, "no such report")
        return jsonify({"ok": True, "report": row})

    @app.get(PREFIX + "/shot/<int:rid>.jpg")
    def shot(rid):
        if not logged_in():
            return redirect("/admin/login")
        with closing(connect()) as conn:
            row = conn.execute("SELECT shot FROM reports WHERE id = ?", (rid,)).fetchone()
        path = os.path.join(shots, "%d.jpg" % rid)
        if row is None or not row["shot"] or not os.path.isfile(path):
            return fail(404, "no screenshot")
        resp = send_file(path, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Content-Security-Policy"] = SHOT_CSP   # opened alone in a new tab
        return resp

    @app.post(PREFIX + "/api/delete")
    @control
    def api_delete():
        try:
            ids = parse_ids(request.form.get("ids", ""))
        except ValueError as exc:
            return fail(400, str(exc))
        return removed("id IN (%s)" % ",".join("?" * len(ids)), ids, "%d asked" % len(ids))

    @app.post(PREFIX + "/api/delete_tag")
    @control
    def api_delete_tag():
        # Only what the page had loaded (id <= upto): reports that arrived since,
        # possibly honest ones behind the same carrier NAT, stay.
        tag = request.form.get("tag", "")
        if not TAG.fullmatch(tag):
            return fail(400, "tag must be 8 hex digits")
        try:
            upto = _int(request.form.get("upto"), None, 1, 10 ** 9 - 1)
        except ValueError:
            upto = None
        if upto is None:
            return fail(400, "upto must be the highest report number the page loaded")
        return removed("source = ? AND id <= ?", (tag, upto), "source %s to #%d" % (tag, upto),
                       newer=("source = ? AND id > ?", (tag, upto)))

    @app.after_request
    def harden(resp):
        resp.headers.setdefault("Content-Security-Policy", ADMIN_CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    for code, message in ((404, "not found"), (405, "method not allowed"),
                          (413, "request too large"), (500, "internal error")):
        app.register_error_handler(code, lambda _e, c=code, m=message: fail(c, m))
    return app


def _state_key(state):
    """The tag key when the panel has no secret: random, kept beside the DB."""
    path = os.path.join(state, "source.key")
    try:
        with open(path, "rb") as fh:
            key = fh.read()
        if len(key) == 32:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key
