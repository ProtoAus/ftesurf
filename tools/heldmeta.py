"""Strict aircell1 metadata grammar; structural integrity is not replay acceptance."""
from dataclasses import dataclass
import hashlib
import io
import math
import re
import struct

BASE_VERSION = 14
NATIVE_VERSION = 15  # New relative MC semantics, distinct ordinary/native framing.
NATIVE_VERSIONS = (13, 15)  # Historical13 keeps its original interpretation.
MAX_EVENTS = 16384
MAX_PIECES = 4096
MAX_BYTES = 2 * 1024 * 1024
MAX_LINE = 8192
TF_NONCE = 131072


def fields(text):
    return tuple(tuple(item.split(":")) for item in text.split())


PREFIX = fields("generation:G ordinal:L message:L execution:L")
PHYS = fields("""
origin_x:F origin_y:F origin_z:F velocity_x:F velocity_y:F velocity_z:F
safeorigin_x:F safeorigin_y:F safeorigin_z:F safeorigin_known:U ground:U groundent:I
hullmins_x:F hullmins_y:F hullmins_z:F hullmaxs_x:F hullmaxs_y:F hullmaxs_z:F
pmtype:U jump_held:U jump_msec:I waterjumptime:F gravitydir_x:F gravitydir_y:F gravitydir_z:F
basevelocity_x:F basevelocity_y:F basevelocity_z:F onladder:U capsule:U surfacefriction:F
ducktime:F ducking:U ducked:U msec_carry:F oldbuttons:I stamina:F rampoff:F boardcount:F
rampcontact:F srcladder:U srcladdernormal_x:F srcladdernormal_y:F srcladdernormal_z:F
portaloffset_x:F portaloffset_y:F portaloffset_z:F viewheight:F waterlevel:U watertype:I raw_moveticks:L tickused:F
portalcrossings:U numtouch:U
""")
OBS = fields("""
origin_x:F origin_y:F origin_z:F velocity_x:F velocity_y:F velocity_z:F ground:U
hullmins_x:F hullmins_y:F hullmins_z:F hullmaxs_x:F hullmaxs_y:F hullmaxs_z:F
raw_moveticks:L tickused:F msec_carry:F surfacefriction:F ducktime:F ducking:U ducked:U
stamina:F rampoff:F boardcount:F rampcontact:F srcladder:U srcladdernormal_x:F
srcladdernormal_y:F srcladdernormal_z:F portaloffset_x:F portaloffset_y:F portaloffset_z:F
""")
CLOCK_NAMES = """
starttick startsec startwall tickcarry lastmt lastsec freeze frzon frzat frzmt frzcarry
frzticks frzsec state ticks elapsed ckwall ckwt ckgaps ckncr ckcb ckcr ckd cktr ckpk ckup
cku ckskip resumesec lastorg_x lastorg_y lastorg_z packet counted flags frame
""".split()
CLOCK = tuple(("clock_" + name, "F") for name in CLOCK_NAMES)
PIN_NAMES = """
pmsrcver physmode pmtype gamespeed hullx0 hully0 hullx1 hully1 capsule svmaxvel trisoup rotboxes portalcsg gravity stopspeed maxspeed spectatormaxspeed accelerate airaccelerate wateraccelerate friction waterfriction flyfriction entgravity bunnyspeedcap watersinkspeed ktjump edgefriction walljump slidefix airstep pground stepdown slidyslopes autobunny bunnyfriction stepheight ticrate maxairspeed jumpvelocity standablenormal bounce maxvelocity standheight duckheight duckspeed viewheight duckviewheight noclipspeed stamina staminajumpcost staminalandcost staminarecovery normalizejump jumpaddrise jumpzoffset walkspeed groundtracedist bumpcount snaptoground groundquadrants fixslopes fixedges fixrampbugs rampretrace viewscale ladders ladderdampen ladderangle slide
""".split()
PIN_UNSIGNED = {"pmsrcver", "physmode", "pmtype", "capsule", "walljump", "slidefix",
                "airstep", "pground", "stepdown", "slidyslopes", "autobunny", "bunnyfriction"}
CTX = tuple(("ctx_" + name, "U" if name in PIN_UNSIGNED else "I" if name == "stepheight" else "F")
            for name in PIN_NAMES) + fields("""
ctx_hullmins_z:F ctx_hullmaxs_z:F ctx_hullnum:I ctx_geomtype:I ctx_coordtype:U ctx_flags:U
ctx_gravitydir_x:F ctx_gravitydir_y:F ctx_gravitydir_z:F ctx_numphysent:U
ctx_trisoup_i:I ctx_rotboxes_i:I ctx_portalcsg_i:I ctx_excuse:F ctx_slow:F ctx_hyst:F
ctx_allow:F ctx_freecredits:F ctx_gap:F
""")
SCHEMAS = {
    "hctx": PREFIX + fields("context:U world:D zone:D engine:D plugin:D progs:D rules:U") + CTX,
    "hinit": PREFIX + fields("context:U") + PHYS + CLOCK,
    "hscope": PREFIX + fields("kind:U phase:U time:F frametime:F"),
    "hpre": PREFIX + fields("phase:U time:F frametime:F"),
    "hmove": PREFIX + fields("effective_msec:F gamespeed:F context:U pmtype:U ownerkind:U ownerindex:U"),
    "hordinary": PREFIX + fields("ownerkind:U ownerindex:U context:U pmtype:U"),
    "hdone": PREFIX + fields("ticksrun:U carry:F raw_moveticks:L"),
    "hpost": PREFIX + fields("phase:U time:F frametime:F"),
    "hentry": PREFIX + fields("saved_movetype:I"),
    "hmaint": PREFIX + fields("site:U"),
    "hrelease": PREFIX + fields("restored_movetype:I"),
    "hfreeze": PREFIX + CLOCK,
    "hthaw": PREFIX + CLOCK,
    "hobs": PREFIX + fields("boundary:U") + OBS,
    "hpend": PREFIX + fields("last_execution:L"),
    "hterminal": PREFIX + fields("closekind:U") + CLOCK,
    "hseal": PREFIX + fields("""
first_execution:L last_execution:L executions:L pre_enters:L pre_exits:L movers:L
completions:L post_enters:L post_exits:L messages:L commands:L scene_fences:L
control_events:L effect_dispatches:L ledger:D execution_ledger:D qualification:U
"""),
    "hfail": fields("generation:G status:U"),
}
WIRE_FAMILIES = frozenset(name.encode("ascii") for name in SCHEMAS)
ARITIES = {"hctx": 100, "hinit": 95, "hscope": 8, "hpre": 7, "hmove": 10,
           "hordinary": 8, "hdone": 7, "hpost": 7, "hentry": 5, "hmaint": 5,
           "hrelease": 5, "hfreeze": 40, "hthaw": 40, "hobs": 36, "hpend": 5,
           "hterminal": 41, "hseal": 21, "hfail": 2}
assert len(PHYS) == 54 and len(OBS) == 31 and len(CLOCK) == 36 and len(CTX) == 89
assert {key: len(value) for key, value in SCHEMAS.items()} == ARITIES
assert all(len({name for name, _ in schema}) == len(schema) for schema in SCHEMAS.values())
WIDTHS = {"U": 8, "I": 8, "F": 8, "L": 16, "G": 32, "D": 64}
HEX = re.compile(r"[0-9a-f]+\Z")
NONNEGATIVE_ZERO = {"effective_msec", "gamespeed", "frametime", "carry", "msec_carry",
                    "tickused", "ctx_ticrate", "ctx_gamespeed", "clock_frzcarry"}
BOOLS = {"safeorigin_known", "ground", "jump_held", "onladder", "capsule", "ducking",
         "ducked", "srcladder", "surfing", "ctx_capsule"}


class Malformed(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    family: str
    values: dict
    canonical: bytes


def parse_record(line):
    if not isinstance(line, bytes) or len(line) > MAX_LINE or not line.endswith(b"\n"):
        raise Malformed("line framing or bound")
    try:
        text = line[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise Malformed("non-ASCII record") from exc
    tokens = text.split(" ")
    schema = SCHEMAS.get(tokens[0])
    if schema is None or len(tokens) != len(schema) + 1:
        raise Malformed("family or arity")
    values = {}
    canonical = bytearray(tokens[0].encode("ascii") + b"\0")
    for token, (name, kind) in zip(tokens[1:], schema):
        if len(token) != WIDTHS[kind] or not HEX.fullmatch(token):
            raise Malformed("noncanonical " + name)
        raw = bytes.fromhex(token)
        canonical.extend(raw)
        if kind == "F":
            value = struct.unpack(">f", raw)[0]
            if not math.isfinite(value):
                raise Malformed("nonfinite " + name)
            if name in NONNEGATIVE_ZERO and (value < 0 or token == "80000000"):
                raise Malformed("negative timing " + name)
        elif kind in ("G", "D"):
            value = raw
        else:
            value = int.from_bytes(raw, "big", signed=(kind == "I"))
        if name in BOOLS and value not in (0, 1):
            raise Malformed("nonboolean " + name)
        values[name] = value
    return Record(tokens[0], values, bytes(canonical))


@dataclass(frozen=True)
class Witness:
    generation: bytes
    records: tuple
    status: str


def parse_witness(lines):
    """Validate all metadata, independently of ordinary rows and model admission."""
    records = []
    size = 0
    for line in lines:
        if not isinstance(line, bytes):
            raise Malformed("nonbyte witness")
        size += len(line)
        if size > MAX_BYTES or len(records) >= MAX_EVENTS:
            raise Malformed("witness bound")
        records.append(parse_record(line))
    if not records:
        raise Malformed("missing witness")
    generation = records[0].values["generation"]
    if any(r.values["generation"] != generation for r in records):
        raise Malformed("mixed generation")
    if records[0].family == "hfail":
        if len(records) != 1 or records[0].values["status"] not in (1, 2):
            raise Malformed("failed witness retains detail")
        return Witness(generation, tuple(records), "unsupported" if
                       records[0].values["status"] == 1 else "incomplete")
    if records[0].family != "hctx" or records[-1].family != "hseal":
        raise Malformed("unsealed witness")
    ledger = hashlib.sha256(b"FTESURF-aircell1-ledger-1").digest()
    execution_ledger = hashlib.sha256(b"FTESURF-aircell1-exec-1").digest()
    stack = []
    callback = None
    maintenance = 0
    stage = None
    message = execution = initialized = entered = released = frozen = thawed = obs = terminal = 0
    pending = False
    sealed = False
    nonce_acked = False
    current = None
    counts = dict.fromkeys(("pre_enters", "pre_exits", "movers", "completions",
                           "post_enters", "post_exits", "messages", "commands",
                           "scene_fences", "control_events"), 0)
    aliases = set()
    post_thaw_moves = 0
    for ordinal, record in enumerate(records, 1):
        f, v = record.family, record.values
        if sealed or f == "hfail" or v["ordinal"] != ordinal:
            raise Malformed("event ordinal or failed detail")
        p = next((p for kind, p in reversed(stack) if kind == 1), 0)
        if f == "hscope" and v["kind"] == 1 and v["phase"] == 1:
            p = message + 1
        if v["message"] != p:
            raise Malformed("message association")
        if pending and stack and not (f == "hscope" and v["kind"] == 1 and v["phase"] == 2):
            raise Malformed("event after packet closure")
        if f in ("hscope", "hpost", "hpend", "hseal", "hfreeze", "hthaw", "hterminal"):
            if v["execution"]:
                raise Malformed("unassociated event execution")
        elif f in ("hentry", "hrelease", "hmaint", "hobs"):
            if v["execution"] != (execution + 1 if callback == "pre" else 0):
                raise Malformed("control execution association")
        if "clock_flags" in v:
            flags = v["clock_flags"]
            if flags < 0 or flags > 0xffffffff or flags != int(flags):
                raise Malformed("clock flags word")
            if bool(int(flags) & TF_NONCE) != nonce_acked:
                raise Malformed("nonce flag without its validated command horizon")
        if f == "hseal":
            if stack or callback or maintenance or stage or not terminal or obs != 4:
                raise Malformed("open terminal scope")
            expected = dict(counts, first_execution=1, last_execution=execution,
                            executions=execution, effect_dispatches=0, qualification=1)
            if any(v[key] != value for key, value in expected.items()):
                raise Malformed("independent coverage counter")
            if v["ledger"] != ledger or v["execution_ledger"] != execution_ledger:
                raise Malformed("ledger digest")
            if not (initialized == entered == released == frozen == thawed == 1) or not post_thaw_moves:
                raise Malformed("incomplete lifecycle")
            sealed = True
            continue
        ledger = hashlib.sha256(ledger + record.canonical).digest()
        if terminal:
            if f not in ("hpost", "hpend", "hscope") or (f in ("hpost", "hscope") and v["phase"] != 2):
                raise Malformed("execution after terminal")
        if f == "hctx":
            if ordinal != 1 or v["context"] != 1 or v["execution"] or v["rules"] != 1:
                raise Malformed("context placement or unsupported rules")
        elif f == "hscope":
            kind, phase = v["kind"], v["phase"]
            if kind not in (1, 2, 3, 4) or phase not in (1, 2) or callback or stage:
                raise Malformed("scope transition")
            if kind != 1:
                counts["scene_fences"] += 1
            if phase == 1:
                if kind == 1:
                    if stack or message >= MAX_PIECES:
                        raise Malformed("message nesting or bound")
                    message += 1
                    counts["messages"] += 1
                    pending = False
                elif kind == 2 and stack:
                    raise Malformed("frame nesting")
                elif kind in (3, 4):
                    if not stack or stack[-1][0] != 1:
                        raise Malformed("command envelope")
                    counts["commands"] += 1
                stack.append((kind, v["message"]))
            else:
                if not stack or stack.pop() != (kind, v["message"]):
                    raise Malformed("unpaired scope")
                if kind == 1:
                    if not pending:
                        raise Malformed("missing packet closure")
                    pending = False
                if kind == 4:
                    nonce_acked = True
        elif f == "hinit":
            if initialized or execution or callback or stage or len(stack) != 1 or stack[0][0] != 1 or v["execution"] != 1 or v["context"] != 1:
                raise Malformed("initial horizon")
            initialized = 1
        elif f == "hpre":
            counts["scene_fences"] += 1
            if not initialized or not stack or stack[-1][0] != 1 or v["execution"] != execution + 1:
                raise Malformed("PreThink execution")
            if v["phase"] == 1 and not callback and not stage:
                callback = "pre"
                maintenance = 0
                counts["pre_enters"] += 1
            elif v["phase"] == 2 and callback == "pre":
                if maintenance != (1 if entered and not released else 0):
                    raise Malformed("PreThink maintenance")
                callback = None
                maintenance = 0
                stage = "prepared"
                counts["pre_exits"] += 1
            else:
                raise Malformed("PreThink pairing")
        elif f in ("hmove", "hordinary"):
            if stage != "prepared" or callback or v["execution"] != execution + 1 or v["context"] != 1:
                raise Malformed("mover coverage")
            if execution >= MAX_PIECES or v["pmtype"] != (5 if entered and not released else 0):
                raise Malformed("mover route")
            if f == "hmove" and (not 0 <= v["effective_msec"] <= 50 or v["gamespeed"] != 1):
                raise Malformed("effective timing")
            if v["ownerkind"] not in (1, 2, 3) or (v["ownerkind"] == 3 and (v["ownerindex"] or f != "hmove")):
                raise Malformed("ordinary alias")
            alias = (v["ownerkind"], v["ownerindex"])
            if alias[0] != 3:
                if alias in aliases:
                    raise Malformed("duplicate ordinary alias")
                aliases.add(alias)
            execution += 1
            if thawed:
                post_thaw_moves += 1
            counts["movers"] += 1
            current = record.canonical
            stage = "moved"
        elif f == "hdone":
            if stage != "moved" or v["execution"] != execution:
                raise Malformed("mover completion")
            if v["carry"] < 0:
                raise Malformed("negative carry")
            execution_ledger = hashlib.sha256(execution_ledger + current + record.canonical).digest()
            counts["completions"] += 1
            stage = None
        elif f == "hpost":
            counts["scene_fences"] += 1
            if not initialized or not stack or stack[-1][0] != 1 or stage or v["execution"]:
                raise Malformed("PostThink placement")
            if v["phase"] == 1 and not callback:
                callback = "post"
                maintenance = 0
                counts["post_enters"] += 1
            elif v["phase"] == 2 and callback == "post":
                if maintenance != (6 if entered and not released else 0):
                    raise Malformed("PostThink maintenance")
                callback = None
                maintenance = 0
                counts["post_exits"] += 1
            else:
                raise Malformed("PostThink pairing")
        elif f == "hentry":
            if entered or not execution or obs != 1 or v["saved_movetype"] != 3 or callback or not stack or stack[-1][0] != 3:
                raise Malformed("pin entry")
            if records[ordinal - 2].family != "hobs" or records[ordinal - 2].values["boundary"] != 1:
                raise Malformed("entry observation fence")
            entered = 1
            counts["control_events"] += 1
            counts["scene_fences"] += 1
        elif f == "hrelease":
            if not entered or released or v["restored_movetype"] != 3 or callback or not stack or stack[-1][0] != 3:
                raise Malformed("pin release")
            released = 1
            counts["control_events"] += 1
            counts["scene_fences"] += 1
        elif f == "hmaint":
            if (not entered or released or v["site"] not in (1, 2, 3) or
                    callback != ("pre" if v["site"] == 1 else "post") or
                    maintenance != (2 if v["site"] == 3 else 0) or
                    (v["site"] == 3 and not frozen)):
                raise Malformed("pin maintenance order")
            maintenance |= 1 << (v["site"] - 1)
            counts["control_events"] += 1
            counts["scene_fences"] += 1
        elif f == "hfreeze":
            if not entered or frozen or callback != "post" or maintenance != 2:
                raise Malformed("freeze accounting")
            frozen = 1
            counts["control_events"] += 1
        elif f == "hthaw":
            if not released or not frozen or thawed or callback != "post":
                raise Malformed("thaw accounting")
            thawed = 1
            counts["control_events"] += 1
        elif f == "hobs":
            if v["boundary"] != obs + 1 or (obs == 1 and not released) or (obs >= 2 and not thawed):
                raise Malformed("observation boundary")
            if obs < 2:
                if callback or not stack or stack[-1][0] != 3:
                    raise Malformed("control observation scope")
                if obs == 1 and records[ordinal - 2].family != "hrelease":
                    raise Malformed("release observation fence")
            elif callback != "post" or (obs == 2 and records[ordinal - 2].family != "hthaw"):
                raise Malformed("accounting observation fence")
            obs += 1
        elif f == "hpend":
            if callback or stage or not stack or stack[-1][0] != 1 or pending or v["last_execution"] != execution:
                raise Malformed("packet closure")
            pending = True
        elif f == "hterminal":
            if terminal or v["closekind"] != 1 or not thawed or obs != 4 or callback != "post":
                raise Malformed("terminal lifecycle")
            if records[ordinal - 2].family != "hobs" or records[ordinal - 2].values["boundary"] != 4:
                raise Malformed("terminal observation fence")
            terminal = 1
        else:
            raise Malformed("unsupported family")
    return Witness(generation, tuple(records), "sealed")


@dataclass(frozen=True)
class Recording:
    ordinary: bytes
    witness: Witness


def _neutral_ride_floor(line):
    """Initial recorder observation only; never a carrier operation or seed."""
    words = line.split()
    if (len(words) != 7 or words[0] != b"ride" or words[3] != b"arm" or
            any(word not in (b"0", b"-0") for word in words[4:])):
        return None
    if any(re.fullmatch(rb"(?:0|[1-9][0-9]{0,7})", word) is None for word in words[1:3]):
        return None
    packet, mover = map(int, words[1:3])
    return (packet, mover) if max(packet, mover) <= 16777216 else None


def is_native_recording(data, version=None):
    """REC15 is mandatory; historical native13 is distinguished from public13 by its namespace."""
    if not isinstance(data, bytes):
        return False
    if version is None:
        try:
            version = int(data.split(b"\n", 1)[0].split()[1])
        except (ValueError, IndexError):
            version = None
    if version == NATIVE_VERSION:
        return True
    body = False
    for line in io.BytesIO(data):
        words = line.split(None, 1)
        if not words:
            continue
        tag = words[0]
        if tag in WIRE_FAMILIES or (body and tag.startswith(b"h") and tag != b"hold"):
            return True
        if tag == b"begin":
            body = True
    return False


def parse_recording(data):
    """Frame native REC13/15 without normalizing witness bytes; never a native verdict.

    Historical13 has a v12 body; native15 follows ordinary14 including park counts.
    ownerindex is the combined zero-based
    in/fzin occurrence, not a packet/tick or a per-family counter.
    """
    if not isinstance(data, bytes) or not any(data.startswith(("FTESURF-REC %d\n" % version).encode("ascii")) for version in NATIVE_VERSIONS):
        raise Malformed("native REC%d header framing" % NATIVE_VERSION)
    stream = io.BytesIO(data)
    stream.readline()
    body = ended = False
    suffix_at = None
    rowkinds = []
    seeds = 0
    incompatible = False
    floor_seen = False
    floor_key = None
    for line in stream:
        tokens = line.split()
        if not tokens:
            continue
        tag = tokens[0]
        if tag in WIRE_FAMILIES or (body and tag.startswith(b"h") and tag != b"hold"):
            if not body or not ended:
                raise Malformed("witness before ordinary close")
            suffix_at = stream.tell() - len(line)
            break
        if tag == b"FTESURF-REC" or (body and tag == b"begin"):
            raise Malformed("duplicate ordinary header")
        if not body:
            if tag == b"begin":
                body = True
            continue
        if ended and tag != b"split":
            raise Malformed("ordinary record after end")
        if tag == b"end":
            ended = True
        elif tag in (b"in", b"fzin"):
            if not rowkinds and floor_seen:
                key = None
                if (tag == b"in" and len(tokens) == 12 and
                        all(re.fullmatch(rb"[+-]?[0-9]{1,63}", word) and len(word) < 64
                            for word in tokens[1:3])):
                    key = tuple(map(int, tokens[1:3]))
                if key is None or key != floor_key:
                    incompatible = True
            # Failed profiles still retain arbitrarily long legacy recordings;
            # keep only enough kinds to prove a sealed profile exceeded its cap.
            if len(rowkinds) <= MAX_PIECES:
                rowkinds.append(1 if tag == b"in" else 2)
        elif tag == b"seed":
            seeds += 1
        elif tag == b"ride":
            key = _neutral_ride_floor(line)
            if floor_seen or rowkinds or seeds != 1 or key is None:
                incompatible = True
            floor_seen = True
            floor_key = key
        elif tag in (b"pause", b"session", b"retry", b"resume", b"ghost", b"spec", b"portal", b"parkclock"):
            incompatible = True
    if suffix_at is None:
        raise Malformed("missing finalized witness")
    if len(data) - suffix_at > MAX_BYTES:
        raise Malformed("witness bound")
    stream.seek(suffix_at)
    witness = parse_witness(stream)
    if witness.status == "sealed":
        if seeds != 1 or incompatible:
            raise Malformed("sealed profile has incompatible ordinary history")
        if len(rowkinds) > MAX_PIECES:
            raise Malformed("ordinary alias bound")
        alias = 0
        for record in witness.records:
            if record.family not in ("hmove", "hordinary"):
                continue
            v = record.values
            if v["pmtype"] == 5:
                if v["ownerkind"] != 3:
                    raise Malformed("held input must not have an ordinary payload")
            elif v["ownerkind"] == 3:
                raise Malformed("ordinary execution without an input alias")
            if v["ownerkind"] != 3:
                if (alias >= len(rowkinds) or v["ownerindex"] != alias or
                        v["ownerkind"] != rowkinds[alias]):
                    raise Malformed("ordinary alias coverage or order")
                alias += 1
        if alias != len(rowkinds):
            raise Malformed("unowned ordinary input")
    return Recording(data[:suffix_at], witness)
