#!/usr/bin/python3.11 -ISB
"""P1115: install a surfd generation's systemd drop-in without Lex.

Runs as root ONLY as surfd-dropin-install.service (a oneshot), which proto may start with
`sudo -n systemctl start surfd-dropin-install.service` (the sudoers line). As a system unit
it is in root's own cgroup with no terminal of the caller's, so proto cannot pause, freeze
or signal it partway (review 2). Exit 0 from `sudo -n systemctl start` IS success. Any
failure returns 1 and proto cannot read the journal: then STATUS says why -- one
world-readable line naming the candidate it read (its sha256, first 16) and the time, so
a line about another candidate, or older than the start, is not this run's (a start the
start limit refused writes none). The unit is unloaded once it succeeds, so its
InvocationID cannot be read afterwards (review 4).

    python3.11 -ISB surfd_dropin_install.py --dry-run     (anyone: check, install nothing)

It installs CANDIDATE only if it is BYTE FOR BYTE the live drop-in after the one change a
generation cutover needs (tmp/gen's gen_dropin*.py): the new root's state/ and control/ added
to ReadWritePaths and to the preflight's folder list, the pinned generation and the
preflight's target moved to that root, and five ReadOnlyPaths pins appended. The expected
text is rebuilt here from the live file, so nothing else -- no Exec* line above all -- can
get through. The root/manifest checks are consistency checks, not a security boundary:
proto owns those paths (and run.sh) either way. The live file is re-read just before the
swap, so an edit made since the check is not undone (a window of microseconds remains).

Exit: 0 installed, already installed (reloaded if systemd needed it), or would install
(--dry-run); 1 refused, nothing changed; 2 usage or not root; 3 the drop-in is in place but
`systemctl daemon-reload` failed (start the unit again to finish); 4 not installed after an
OSError before the swap, or an internal error.
"""
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

LIVE = "/etc/systemd/system/surfd.service.d/10-guarded-startup.conf"
AGENT_WORK = "/srv/nvme/agent-work"
CANDIDATE = ("surfd-dropin", "candidate.conf")          # under AGENT_WORK, walked without symlinks
OWNER = "proto"                                         # who must own the candidate
LOG = "/var/log/surfd-dropin-install.log"
STATUS = "/run/surfd-dropin-install.status"
LOCK = "/run/surfd-dropin-install.lock"
RELOAD = ["/usr/bin/systemctl", "daemon-reload"]
NEEDS_RELOAD = ["/usr/bin/systemctl", "show", "-p", "NeedDaemonReload", "--value", "surfd.service"]
BACKUPS_KEEP = 20
LOG_MAX = 1 << 20
MSG_MAX = 300
MAX_BYTES = 1 << 20
MAX_LINE = 96 * 1024        # the preflight is one ExecStartPre line: the kernel caps one argument at 128 KiB
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}")
GEN = re.compile(r"[0-9a-f]{40}")
LABEL = re.compile(r"P[0-9]{3,5}")
PINS = ("control/surfd_transition_guard.py", "control/surfd_import_dispatch.py",
        "control/gunicorn.conf.py", "control/manifest.json", "state/manifest.json")
GENPIN = re.compile(r"'generation':'([0-9a-f]{40})'")
TAIL = re.compile(r"# (P[0-9]{3,5}) generation ([0-9a-f]{40}): its fixed control files and manifest\.\n")
BACKUP = re.compile(r"10-guarded-startup\.conf\.pre-([0-9]{8}T[0-9]{6}Z)-[0-9a-f]{8}(\.[0-9]+)?")
TMP = re.compile(r"\.10-guarded-startup\..+\.tmp")
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
NONBLOCK = getattr(os, "O_NONBLOCK", 0)
DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_cand_sha = "-"                         # the candidate this run read, for STATUS


class Refused(Exception):
    pass


def _short(msg):
    msg = str(msg)
    return msg if len(msg) <= MSG_MAX else msg[:MSG_MAX] + "..."


def _once(text, old, new):
    if text.count(old) != 1:
        raise Refused("expected exactly one %r in the live drop-in, found %d" % (old[:70], text.count(old)))
    return text.replace(old, new)


def _plain_root(new):
    return (new.startswith(AGENT_WORK + "/") and NAME.fullmatch(new[len(AGENT_WORK) + 1:]) is not None
            and not new.endswith((".", "-")))


def expected(live, new, gen, label):
    """The live drop-in after one generation's change: root `new`, generation `gen`."""
    if not _plain_root(new):
        raise Refused("new root %r is not one plain name under %s" % (_short(new), AGENT_WORK))
    if not GEN.fullmatch(gen) or not LABEL.fullmatch(label):
        raise Refused("bad generation or label")
    target = re.compile(r"target=Path\('(%s/[^']*)/control/service-filesystem-preflight\.json'\)" % re.escape(AGENT_WORK))
    olds, gens = target.findall(live), GENPIN.findall(live)
    if len(olds) != 1 or len(gens) != 1:
        raise Refused("the live drop-in does not hold one preflight target and one generation pin")
    old = olds[0]
    if new == old or (new + "/") in live or ("'%s'" % new) in live or ('"%s"' % new) in live:
        raise Refused("the new root is already in the live drop-in")
    text = _once(live, " %s/state %s/control\n" % (old, old),
                 " %s/state %s/control %s/state %s/control\n" % (old, old, new, new))
    text = _once(text, "'%s/state', '%s/control']" % (old, old),
                 "'%s/state', '%s/control', '%s/state', '%s/control']" % (old, old, new, new))
    text = _once(text, "'generation':'%s'" % gens[0], "'generation':'%s'" % gen)
    text = _once(text, "target=Path('%s/control/service-filesystem-preflight.json')" % old,
                 "target=Path('%s/control/service-filesystem-preflight.json')" % new)
    text = text.rstrip("\n") + "\n# %s generation %s: its fixed control files and manifest.\n" % (label, gen)
    return text + "".join('ReadOnlyPaths="%s/%s"\n' % (new, p) for p in PINS)


def parse_tail(candidate):
    """(new root, generation, label) from the candidate's last six lines; the root a plain name."""
    lines = candidate.splitlines(keepends=True)
    if len(lines) < 7:
        raise Refused("candidate too short")
    m = TAIL.fullmatch(lines[-6])
    if not m:
        raise Refused("candidate's sixth line from the end is not a generation comment")
    roots = set()
    for line, pin in zip(lines[-5:], PINS):
        p = re.fullmatch(r'ReadOnlyPaths="(%s/[^"/]{1,81})/%s"\n' % (re.escape(AGENT_WORK), re.escape(pin)), line)
        if not p:
            raise Refused("candidate's pin %r is not the expected form" % _short(line))
        roots.add(p.group(1))
    if len(roots) != 1:
        raise Refused("the five pins name more than one root")
    new = roots.pop()
    if not _plain_root(new):
        raise Refused("new root is not one plain name under %s" % AGENT_WORK)
    return new, m.group(2), m.group(1)


def validate(live_bytes, cand_bytes):
    """-> (new root, generation, label), or Refused."""
    try:
        live, cand = live_bytes.decode("ascii"), cand_bytes.decode("ascii")
    except UnicodeDecodeError:
        raise Refused("a drop-in that is not plain ASCII")
    new, gen, label = parse_tail(cand)
    if cand != expected(live, new, gen, label):
        raise Refused("the candidate differs from the live drop-in by more than the generation change")
    if max(len(line) for line in cand.splitlines()) > MAX_LINE:
        raise Refused("a line would pass %d bytes (the preflight's argument limit): prune old generations by hand" % MAX_LINE)
    return new, gen, label


def missing_paths(cand):
    """Sandbox paths the unit needs at start that do not exist (systemd refuses to start then)."""
    paths = []
    for line in cand.splitlines():
        if line.startswith("ReadWritePaths="):
            paths += line[len("ReadWritePaths="):].split()
        elif line.startswith('ReadOnlyPaths="') and line.endswith('"'):
            paths.append(line[len('ReadOnlyPaths="'):-1])
    return [p for p in paths if not p.startswith("-") and not os.path.lexists(p)]   # lexists: review 3


def _openat_chain(parts, final_flags):
    """Open AGENT_WORK/parts... refusing a symlink at every step after AGENT_WORK."""
    fd = os.open(AGENT_WORK, os.O_RDONLY | DIRECTORY | NOFOLLOW)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | DIRECTORY | NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return os.open(parts[-1], final_flags | NOFOLLOW | NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def _read_fd(fd, owner_uid=None):
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refused("not a regular file")
        if st.st_size > MAX_BYTES:
            raise Refused("larger than %d bytes" % MAX_BYTES)
        if owner_uid is not None and (st.st_uid != owner_uid or st.st_nlink != 1):
            raise Refused("the candidate must be %s's own file with one link" % OWNER)
        data = b""
        while len(data) <= MAX_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES:
        raise Refused("larger than %d bytes" % MAX_BYTES)
    return data


def read_candidate():
    import pwd                          # Linux only, as the helper is (the tests also run on Windows)
    try:
        fd = _openat_chain(list(CANDIDATE), os.O_RDONLY)
    except OSError as exc:
        raise Refused("candidate: %s" % _short(exc))
    return _read_fd(fd, pwd.getpwnam(OWNER).pw_uid)


def check_root(new, gen):
    name = new[len(AGENT_WORK) + 1:]
    try:
        for p in PINS:
            _read_fd(_openat_chain([name] + p.split("/"), os.O_RDONLY))
        data = _read_fd(_openat_chain([name, "state", "manifest.json"], os.O_RDONLY))
    except OSError as exc:
        raise Refused("new root: %s" % _short(exc))
    try:
        man = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        raise Refused("the new root's manifest is not JSON")
    if not isinstance(man, dict) or man.get("generation") != gen:
        raise Refused("the new root's manifest names another generation")


def read_live():
    return _read_fd(os.open(LIVE, os.O_RDONLY | NOFOLLOW))


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise OSError("short write")
        view = view[n:]


def sweep():
    """Temp files a killed run left in the drop-in directory (under the lock)."""
    d = os.path.dirname(LIVE)
    for n in os.listdir(d):
        if TMP.fullmatch(n):
            os.unlink(os.path.join(d, n))


def install(live_bytes, cand_bytes, gen):
    """Put cand_bytes in place of live_bytes -> (backup path, [warnings]). Raises Refused or
    OSError only BEFORE the swap, and the live file is then unchanged."""
    d = os.path.dirname(LIVE)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".10-guarded-startup.", suffix=".tmp")
        try:
            os.fchmod(fd, 0o644)
            _write_all(fd, cand_bytes)
            os.fsync(fd)
            if os.fstat(fd).st_size != len(cand_bytes):
                raise OSError("the written size does not match")
        finally:
            os.close(fd)
        with open(tmp, "rb") as f:
            if f.read() != cand_bytes:
                raise OSError("the written file does not read back as the candidate")
        backup = os.path.join(d, "10-guarded-startup.conf.pre-%s-%s" % (stamp, gen[:8]))
        k = 0
        while os.path.lexists(backup + ("" if not k else ".%d" % k)):
            k += 1
        backup += "" if not k else ".%d" % k
        # The live file must still be the one validated, so an edit since is never rolled back;
        # nothing between here and the swap can block.
        if read_live() != live_bytes:
            raise Refused("the live drop-in changed while this ran")
        os.link(LIVE, backup)           # the replaced file itself, byte for byte
        os.replace(tmp, LIVE)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    warnings = []
    try:
        dfd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError as exc:
        warnings.append("fsync of %s: %s" % (d, exc))
    return backup, warnings


def prune(keep):
    """Oldest backups beyond BACKUPS_KEEP, by their timestamp; never `keep`."""
    d = os.path.dirname(LIVE)
    olds = sorted((m.group(1), n) for n in os.listdir(d) for m in [BACKUP.fullmatch(n)] if m)
    olds = [n for _s, n in olds if os.path.join(d, n) != keep]
    for n in olds[:max(0, len(olds) - (BACKUPS_KEEP - 1))]:
        os.unlink(os.path.join(d, n))


def reload():
    try:
        return subprocess.run(RELOAD, stdin=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def needs_reload():
    """systemd holds an older surfd.service than its files (an unknown answer counts as yes)."""
    try:
        r = subprocess.run(NEEDS_RELOAD, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return True
    return r.stdout.strip() != "no"


def _log(line):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX:
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a") as f:
            f.write("%s %s\n" % (datetime.datetime.now(datetime.timezone.utc).isoformat(), line))
    except OSError:
        pass


def _say(code, line, dry=False):
    if not dry:
        _log(line)
        try:
            fd = os.open(STATUS + ".new", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | NOFOLLOW, 0o644)
            with os.fdopen(fd, "w") as f:
                f.write("at %s candidate %s invocation %s exit %d: %s\n" % (
                    datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), _cand_sha,
                    os.environ.get("INVOCATION_ID", "-"), code, line))
            os.replace(STATUS + ".new", STATUS)
        except OSError:
            pass
    try:
        print(line, file=sys.stderr if code else sys.stdout, flush=True)
    except (OSError, ValueError):
        pass
    return code


def _run(dry):
    global _cand_sha
    try:
        # Everything proto controls first, then the live file (root's), last.
        cand_bytes = read_candidate()
        _cand_sha = hashlib.sha256(cand_bytes).hexdigest()[:16]
        new, gen, label = parse_tail(cand_bytes.decode("ascii", "replace"))
        check_root(new, gen)
        live_bytes = read_live()
        if live_bytes == cand_bytes:
            if dry:
                return _say(0, "already installed: %s (dry run: no reload)" % new, dry)
            if not needs_reload():          # review 3: not a reload on demand for whatever is on disk
                return _say(0, "already installed: %s; systemd is up to date" % new)
            ok = reload()
            return _say(0 if ok else 3, "already installed: %s; daemon-reload %s" % (new, "done" if ok else "FAILED"))
        validate(live_bytes, cand_bytes)
        missing = missing_paths(cand_bytes.decode("ascii"))
        if missing:
            raise Refused("%d sandbox path(s) do not exist and the unit would not start: %s"
                          % (len(missing), _short(", ".join(missing[:3]))))
    except (Refused, OSError) as exc:
        return _say(1, "refused: %s" % _short(exc), dry)
    if dry:
        return _say(0, "would install: %s generation %s (%s)" % (new, gen, label), dry)
    try:
        sweep()
        backup, warnings = install(live_bytes, cand_bytes, gen)
    except (Refused, OSError) as exc:
        return _say(1 if isinstance(exc, Refused) else 4, "not installed: %s" % _short(exc))
    ok = reload()
    try:
        prune(backup)
    except OSError as exc:
        warnings.append("prune: %s" % exc)
    for w in warnings:
        _log("warning: %s" % _short(w))
    if not ok:
        return _say(3, "installed %s on disk, but daemon-reload FAILED: start the unit again to finish" % new)
    return _say(0, "installed: %s generation %s (%s); previous drop-in kept as %s; was %s, now %s" % (
        new, gen, label, backup, hashlib.sha256(live_bytes).hexdigest()[:16],
        hashlib.sha256(cand_bytes).hexdigest()[:16]))


def main(argv):
    os.umask(0o022)
    dry = argv[1:] == ["--dry-run"]
    if argv[1:] and not dry:
        print("usage: surfd-dropin-install [--dry-run]", file=sys.stderr)
        return 2
    if not dry and os.geteuid() != 0:
        print("refused: run as surfd-dropin-install.service, or with --dry-run", file=sys.stderr)
        return 2
    lock = None
    try:
        if not dry:
            import fcntl
            lock = os.open(LOCK, os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
        return _run(dry)
    except Exception as exc:                # anything unforeseen is 4, never a silent 1
        return _say(4, "internal error: %s: %s" % (type(exc).__name__, _short(exc)), dry)
    finally:
        if lock is not None:
            os.close(lock)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
