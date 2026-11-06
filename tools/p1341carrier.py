"""CPU-only teleport-carrier falsifier using exact production QC helpers.

Requires an existing qualified fteqcc, dedicated server, and id1/pak0.pak.
--out must be a NEW directory under the caller's owned task root. No install is
modified. The native consumer is inspected, not executed; no real-network claim.
"""
from pathlib import Path
import argparse, hashlib, json, re, shutil, socket, struct, subprocess

BASELINE_FAILURES = frozenset({
    b"mode1 client queues carrier clear", b"mode2 client queues carrier clear",
    b"mode3 client queues carrier clear", b"noclip alone still clears on teleport",
    b"clear discards earlier push queue", b"push after clear does not sum old push",
    b"push after clear replaces unarmed AddOutput", b"relative clear also preserves later push",
})

def compiler_warnings(log):
    return [line for line in log.splitlines()
            if re.search(rb"warning", line, re.I)
            and not re.fullmatch(rb"\s*Done\.\s+0 warnings\s*", line, re.I)]

def grade_runtime(logs, expected_failures):
    results = re.findall(rb"P1341 RESULT checks=(\d+) failures=(\d+)", logs)
    assert expected_failures in (0, 8)
    assert results and all(int(checks) == 42 and int(failed) == expected_failures
                           for checks, failed in results), ("runtime result", results)
    labels = frozenset(re.findall(rb"P1341 FAIL: ([^\r\n]+)", logs))
    assert labels == (BASELINE_FAILURES if expected_failures else frozenset()), ("failure labels", labels)
    return results

p = argparse.ArgumentParser()
p.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
p.add_argument("--out", type=Path, required=True)
p.add_argument("--compiler", type=Path, required=True)
p.add_argument("--server", type=Path, required=True)
p.add_argument("--pak", type=Path, required=True)
p.add_argument("--expect-failures", type=int, choices=(0, 8), default=0)
a = p.parse_args()
OUT = a.out.resolve()
assert not OUT.exists(), "Keep original evidence immutable"
(OUT / "src").mkdir(parents=True)
(OUT / "ftesurf/maps").mkdir(parents=True)
client = (a.source / "src/client/cl_triggers.qc").read_text(encoding="utf8")
server = (a.source / "src/server/sv_entities.qc").read_text(encoding="utf8")

def function(text, name):
    m = re.search(r"(?ms)^(?:void|float)\([^\n]*\) " + name + r" =\n\{.*?^\};", text)
    assert m, name
    return m.group()

names = ["TG_FireTeleport", "TG_FireRelTele", "TG_FirePush"]
if "void() TG_ClearCarrier =" in client:
    names.insert(0, "TG_ClearCarrier")
helpers = "\n\n".join(function(client, n) for n in names)
tele = function(server, "trigger_teleport_touch")
mode = re.search(r"(?s)\tvmode = SV_Key2\(self.VelocityMode, self.velocitymode\);.*?\t\tSV_ClearCarrier\(other\);", tele).group()
constants = "\n".join(line for line in client.splitlines() if re.match(r"#define TG_(?:PM_|BUTTON_|SF_)", line))
prefix = r'''
#define TG_MAX 4
#define TG_TT_MAX 4
#define STAT_HEALTH 0
#define getstatf TestGetStat
#define checkcommand TestCommand
float test_health, test_dest, test_landmark, test_edges;
float test_checks, test_failures;
float(float stat) TestGetStat = { return test_health; };
float(string command) TestCommand = { return 1; };
float(string name) TT_Find =
{
    if (strcmp(name, "dest") == 0 && test_dest) return 0;
    if (strcmp(name, "mark") == 0 && test_landmark) return 1;
    return -1;
};
float(float i, float seq) TG_IOEdge = { test_edges = test_edges + 1; return 1; };
float(float a, float b) TestMin = { if (a < b) return a; return b; };
#define min TestMin
.float run_basevel_armed;
.vector run_basevel;
.string VelocityMode, velocitymode, SetSpeed, setspeed;
float(string a, string b) SV_Key2 = { if (a != "") return stof(a); return stof(b); };
'''
# Copy the real declarations for all three helpers, without unrelated functions/tables.
prefix += constants + "\n"
declarations = client[client.index("vector predmove_org0;"):client.index("// load census")]
prefix += declarations
prefix += "\nfloat tg_bvel_ok, tg_c_nodest;\n"
if not re.search(r"float\s+tg_carrier_cleared;", prefix):
    prefix += "float tg_carrier_cleared;\n"
prefix += function(server, "SV_ClearCarrier") + "\n"
prefix += "void(entity dest) ServerMode =\n{\nlocal float vmode;\n" + mode + "\n};\n"
tests = r'''
void(float ok, string label) Check =
{
    test_checks = test_checks + 1;
    if (!ok)
    {
        test_failures = test_failures + 1;
        bprint(2, strcat("P1341 FAIL: ", label, "\n"));
    }
};
void() Setup =
{
    test_health = 100; test_dest = 1; test_landmark = 0; test_edges = 0;
    predmove_pmtype = 0; predmove_buttons = 0; predmove_onground = 1;
    predmove_org = '10 20 30'; predmove_vel = '200 100 -40';
    predmove_basevel = '0 0 0'; predmove_bvfired = 0;
    predmove_bvset = '9 8 7'; predmove_bvsetflag = 0;
    predmove_offset = 0; tg_pusharmed = 0; tg_pushvec = '0 0 0';
    tg_carrier_cleared = 0; tg_bvel_ok = 1;
    tg_target[0] = "dest"; tg_landmark[0] = ""; tg_flags[0] = 0;
    tg_vmode[0] = 0; tg_uselm[0] = 0; tg_snapv[0] = 0; tg_tspeed[0] = 300;
    tt_org[0] = '1000 2000 3000'; tt_ang[0] = '0 0 0'; tt_org[1] = '1 2 3';
    tg_flags[2] = TG_SF_TRIGGER_CLIENTS; tg_speed[2] = 400; tg_pushdir[2] = '0 0 0';
    self.VelocityMode = "0"; self.velocitymode = ""; self.SetSpeed = "300";
    other.run_basevel = '100 20 0'; other.run_basevel_armed = 1;
    other.velocity = '200 100 -40';
};
void() worldspawn =
{
    local float m, hit;
    local entity dest;
    self = spawn(); other = spawn(); dest = spawn();
    for (m = 0; m <= 3; m = m + 1)
    {
        Setup(); tg_vmode[0] = m; self.VelocityMode = ftos(m);
        ServerMode(dest);
        hit = TG_FireTeleport(0, 100);
        Check(hit, sprintf("mode%g teleport acted", m));
        Check(predmove_org == '1000 2000 3001', sprintf("mode%g destination", m));
        Check(predmove_vel == other.velocity, sprintf("mode%g velocity parity", m));
        if (m == 0)
            Check(!predmove_bvsetflag && other.run_basevel == '100 20 0', "keep mode preserves carrier on both");
        else
        {
            Check(other.run_basevel == '0 0 0' && !other.run_basevel_armed, sprintf("mode%g server clear acts", m));
            Check(predmove_bvsetflag && predmove_bvset == '0 0 0', sprintf("mode%g client queues carrier clear", m));
        }
    }
    Setup(); tg_vmode[0] = 3; tg_tspeed[0] = 0; self.VelocityMode = "3"; self.SetSpeed = "0";
    ServerMode(dest); TG_FireTeleport(0, 101);
    Check(vlen(predmove_vel - other.velocity) < 0.001, "mode3 inferred speed unchanged");
    for (m = 0; m <= 3; m = m + 1)
    {
        Setup(); tg_landmark[0] = "mark"; test_landmark = 1; tg_vmode[0] = m;
        hit = TG_FireTeleport(0, 102);
        Check(hit && predmove_org == '1009 2018 3027', sprintf("landmark%g acted", m));
        Check(!predmove_bvsetflag && predmove_vel == '200 100 -40', sprintf("landmark%g preserves", m));
    }
    Setup(); tg_vmode[0] = 1; test_dest = 0;
    Check(!TG_FireTeleport(0, 103) && !predmove_bvsetflag && test_edges == 1, "missing destination keeps carrier after IO");
    Setup(); tg_vmode[0] = 1; test_health = 0;
    Check(!TG_FireTeleport(0, 104) && !predmove_bvsetflag && !test_edges, "dead gate keeps carrier");
    Setup(); tg_vmode[0] = 1; tg_flags[0] = 2;
    Check(!TG_FireTeleport(0, 105) && !predmove_bvsetflag && !test_edges, "spawnflag gate keeps carrier");
    Setup(); tg_vmode[0] = 1; predmove_pmtype = TG_PM_SPECTATOR; predmove_buttons = TG_BUTTON_JUMP;
    Check(!TG_FireTeleport(0, 106) && !predmove_bvsetflag && !test_edges, "noclip jump bypass keeps carrier");
    Setup(); tg_vmode[0] = 1; predmove_pmtype = TG_PM_SPECTATOR;
    Check(TG_FireTeleport(0, 107) && predmove_bvsetflag, "noclip alone still clears on teleport");
    Setup(); tg_vmode[0] = 2; tg_bvel_ok = 0;
    Check(TG_FireTeleport(0, 108) && !predmove_bvsetflag && predmove_bvset == '9 8 7', "old engine global untouched");
    Setup(); tg_vmode[0] = 1; TG_FirePush(2, 109);
    Check(predmove_bvfired && tg_pusharmed && predmove_basevel == '400 0 0', "push-before-clear control acts");
    TG_FireTeleport(0, 109);
    Check(!predmove_bvfired && !tg_pusharmed && predmove_basevel == '0 0 0' && tg_pushvec == '0 0 0', "clear discards earlier push queue");
    Setup(); tg_vmode[0] = 1; TG_FireTeleport(0, 110); TG_FirePush(2, 110);
    Check(predmove_bvfired && predmove_basevel == '400 0 0' && !predmove_bvsetflag, "later push survives earlier clear");
    Setup(); tg_vmode[0] = 1; TG_FirePush(2, 111); TG_FireTeleport(0, 111); TG_FirePush(2, 111);
    Check(predmove_basevel == '400 0 0' && !predmove_bvsetflag, "push after clear does not sum old push");
    Setup(); tg_vmode[0] = 1; TG_FireTeleport(0, 112);
    predmove_bvset = '25 0 0'; predmove_bvsetflag = 1;
    Check(!predmove_bvfired && predmove_bvset == '25 0 0', "later AddOutput may refill clear");
    TG_FirePush(2, 112);
    Check(!predmove_bvsetflag && predmove_basevel == '400 0 0', "push after clear replaces unarmed AddOutput");
    Setup(); tg_ent[1] = spawn();
    Check(TG_FireRelTele(1, 113) && predmove_bvsetflag && predmove_bvset == '0 0 0', "relative clear control acts");
    TG_FirePush(2, 113);
    Check(predmove_bvfired && predmove_basevel == '400 0 0' && !predmove_bvsetflag, "relative clear also preserves later push");
    bprint(2, sprintf("P1341 RESULT checks=%g failures=%g\n", test_checks, test_failures));
};
void() main = {};
void() StartFrame = {};
void() SetNewParms = {};
void() SetChangeParms = {};
void() ClientConnect = {};
void() PutClientInServer = {};
void() ClientDisconnect = {};
void() ClientKill = {};
void() PlayerPreThink = {};
void() PlayerPostThink = {};
void() SpectatorConnect = {};
void() SpectatorThink = {};
void() SpectatorDisconnect = {};
'''
# Unlike the earlier single-helper fixture, this module has many unrelated globals.
# Retain declarations only for identifiers referenced by the extracted helpers/tests.
used = helpers + tests
kept = []
for line in declarations.splitlines():
    match = re.match(r"(vector|float|entity|string)\s+([^;]+);", line)
    if match:
        decls = [d.strip() for d in match[2].split(",") if re.search(r"\b" + d.strip().split("[")[0] + r"\b", used)]
        if decls:
            kept.append(match[1] + " " + ", ".join(decls) + ";")
    elif line.startswith("#define"):
        kept.append(line)
prefix = prefix.replace(declarations, "\n".join(kept) + "\n")
shutil.copy2(a.source / "src/defs/sv_defs.qc", OUT / "src/defs.qc")
(OUT / "src/test.qc").write_text(prefix + helpers + tests, encoding="utf8")
(OUT / "src/progs.src").write_text("../ftesurf/qwprogs.dat\ndefs.qc\ntest.qc\n", encoding="utf8")
compiler = a.compiler.resolve()
r = subprocess.run([str(compiler), "-srcfile", "progs.src"], cwd=OUT / "src", capture_output=True, timeout=30)
(OUT / "compile.log").write_bytes(r.stdout + r.stderr)
assert r.returncode == 0, "QC compile failed; preserved compile.log"
assert not compiler_warnings(r.stdout + r.stderr), "Unit QC has warnings; preserved compile.log"
exe = OUT / "fteqwsv64.exe"
shutil.copy2(a.server, exe)
with a.pak.open("rb") as pak:
    magic, offset, size = struct.unpack("<4sii", pak.read(12))
    assert magic == b"PACK" and size % 64 == 0
    pak.seek(offset); directory = pak.read(size)
    entry = next(struct.unpack("<56sii", directory[i:i+64]) for i in range(0, size, 64) if directory[i:i+56].split(b"\0", 1)[0] == b"maps/start.bsp")
    pak.seek(entry[1]); body = pak.read(entry[2]); assert len(body) == entry[2]
(OUT / "ftesurf/maps/start.bsp").write_bytes(body)
(OUT / "default.fmf").write_text('FTEMANIFEST 1\nGAME FTESurfCarrierUnit\nNAME "Carrier synthetic unit"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG unused\n', encoding="utf8")
(OUT / "ftesurf/unit.cfg").write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nlog_enable 1\nlog_developer 1\nlog_name carrier-unit\ndeveloper 1\nsv_public 0\nsv_progs qwprogs.dat\nmap start\nquit\n', encoding="utf8")
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
    probe.bind(("127.0.0.1", 27593))
command = [str(exe), "-manifest", str(OUT / "default.fmf"), "-basedir", str(OUT), "-port", "27593", "+exec", "unit.cfg"]
(OUT / "inputs.json").write_text(json.dumps({"command": command, "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(), "helpers_sha256": hashlib.sha256(helpers.encode()).hexdigest(), "source_sha256": hashlib.sha256(client.encode()).hexdigest()}, indent=2) + "\n")
with (OUT / "process.log").open("wb") as log:
    r = subprocess.Popen(command, cwd=OUT, stdout=log, stderr=subprocess.STDOUT)
    (OUT / "owned-pid.json").write_text(json.dumps({"pid": r.pid, "image": str(exe)}) + "\n")
    try: code = r.wait(timeout=45)
    except subprocess.TimeoutExpired:
        r.terminate(); r.wait(timeout=10); raise
logs = b"\n".join(f.read_bytes() for f in (OUT / "ftesurf").rglob("*.log")) + (OUT / "process.log").read_bytes()
(OUT / "combined.log").write_bytes(logs)
assert code == 0, ("owned server exit", code)
results = grade_runtime(logs, a.expect_failures)
print("Actual QC VM checks/failures:", results[0][0].decode(), results[0][1].decode(), "; process exit0; native/network acceptance NOT claimed")
