# POSIX pre-import transition fence (offline preparation only)

This stdlib-only helper is **not a deployment or migration driver**. It never
imports surfd, opens a database/cache, installs source, edits a scheduler, starts
an unapproved candidate, or restores anything. P717 live schema18→19 remains blocked on
inventory/enforced coverage, quiescent candidate start, coordinated recovery,
external acceptance and native-submit no-loss prerequisites. Nothing here is live
transition authorization.

## Enforcement boundary

Every participating launch must use `surfd_transition_guard.py launch` **before
starting application Python**. The guard itself runs in a trusted stdlib Python
interpreter; that interpreter is not the application interpreter. Use an isolated
invocation such as `/usr/bin/python3 -I /absolute/tools/surfd_transition_guard.py`.
Install/control that interpreter and this script independently of mutable app
source; do not put application modules on the guard interpreter's import path.

The owner must exclude direct/manual unwrapped launches and park all uncovered
services, worker recycling, scheduler and restart paths. This is cooperative
admission, not an OS sandbox: the same UID can bypass it, change its files, close
inherited descriptors, or run Python directly. The test's bypass control proves
that limitation. A previously running unguarded process is not drained. A daemon
that closes inherited FDs or detaches is unsupported; configure foreground
processes and retain the inherited admission FD throughout their lifetime. In a
master/worker model every importing descendant must retain it, or every new
worker must separately enter the guard. Live gunicorn/run.sh coverage is NOT
implemented or established.

The state directory must be exclusively operator-controlled, owned by the
invoking UID, mode700, on a local filesystem with working POSIX flock and fsync.
State/control files are mode600, owner-owned, regular, single-link. Source hashes
are read through nonblocking, no-follow handles after a regular-file check; FIFOs,
directories and symlinks refuse rather than blocking hash verification. Symlink
components and noncanonical `..` paths are refused, including state roots. Ancestors and source must remain under exclusive
operator control during operations: the helper does not defend against hostile
same-UID concurrent namespace replacement. Do not delete/recreate the lock files
or state directory; doing so can split lock identity. Missing, malformed or
unsafe state refuses admission. Initialization uses exclusive mkdir and will
never overwrite an existing path, even after a partial initialization failure.
Such failures require operator investigation, not automatic reset.

## Minimal interface

All paths are explicit absolute canonical POSIX paths; no owner environment or
configuration is discovered. Example syntax (placeholders, not live commands):

```
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence init --manifest /owned/manifest.json
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence status
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence --timeout 30 close
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence reopen --generation <full-sha> --receipt /owned/acceptance.json
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence launch --generation <full-sha> --route scheduled
```

The immutable manifest has the four required keys below and optionally
`target_schema` and `runtime_profile`. Omitted `target_schema` means **schema19 only**, preserving the
legacy six-file format. Explicit `target_schema` must be the JSON integer `19`
or `20`; booleans, floats (including `20.0`), strings, null and unknown schemas
refuse. The target is never inferred from a receipt or the dependency set.

- `generation`: one lowercase full 40-character SHA.
- `source_home`: one existing canonical source directory, used as application cwd.
- `hashes`: raw SHA256 digests for exactly `surfd.py`, `ksfimport.py`,
  `ksfgrab.py`, `ksfprofile.py`, `tools/ksfconvert.py`, `tools/ksfreplay_info.py`
  for schema19 (legacy or explicit). Schema20 requires exactly those six **plus
  `accounts.py` and `social.py`**. The only optional runtime profile is the literal
  `"runtime_profile":"hid-v1"`, valid only with schema20; it requires exactly those
  eight files **plus `hidupload.py`**. Untagged nine-file sets, tagged missing-file
  sets, unknown profiles and arbitrary extra paths refuse. All hashes are
  checked for candidate, ordinary launch and reopen. This pins the coordinated
  social/KSF group, **not** its complete import closure or application runtime.
  External acceptance must separately pin effective dependency origins, including
  the proof verifier, Steam helper and KSF top-up module, plus configuration.
- `routes`: nonempty object of explicit route names to **complete fixed argv
  arrays**, starting with an absolute real executable path (resolve interpreter
  symlinks first). No user argv suffix, environment override, alternate cache or
  alternate home is accepted. This is an operator-authored allowlist, not an
  automatically approved production route set. Do not allowlist daemonizing,
  arbitrary `-c`, shell, or secondary unguarded launcher commands.

There is one pinned generation per state directory, no generation-changing or
manifest-update command. Schema selection is immutable too. This seam does not
implement old18→new19 or schema19→20 rebinding; no existing guard may be relabeled
or have its locks reset to select schema20. The
synthetic old writer means a cooperative writer admitted *before closure*, not a
real schema18 application. Integration must separately review the generation
handover and installation procedure; never create a second OPEN guard to bypass
an existing CLOSED fence.

Initialization always starts CLOSED. Each close serializes against other
controllers, atomically replaces state with CLOSED and a fresh closure ID, fsyncs
file/directory, then attempts bounded exclusive admission-lock and candidate-lifetime-lock acquisition.
Foreground launches acquire a shared lock, check OPEN/generation/route/source
hashes, and exec the fixed application interpreter **in the same PID**, with the
shared FD inherited. Only a fixed minimal environment (`PATH`, `HOME`,
`PYTHONNOUSERSITE`) is supplied. This is intentionally not yet a surfd environment
loader. Closure is durable before drain starts. Timeout, controller death, stdin
EOF, or dropped lock/transport cannot reopen admission. Success says only that
cooperative FD holders drained; it does not inventory arbitrary host processes.
Power-loss durability depends on the filesystem; no physical power-loss test was
performed.

## Linux CLOSED candidate protocol

`candidate` permits only the literal `server` route in the immutable manifest,
with its complete fixed foreground argv. General `launch` still refuses CLOSED.
It does not interpret a shell, accept additional argv/env, choose an executable,
or discover host configuration. The operator must review the manifest's server
route itself: no daemonization, shell, preload or descriptor-closing launcher.
The manifest-selected schema/hash set, pinned generation and minimal environment
remain fixed throughout the candidate lifetime.
Old writers, boot, cron, manual launches and native-submit exclusion remain an
external obligation, not a claim of this command.

```
python3 -I /trusted/surfd_transition_guard.py --state-dir /owned/fence candidate --generation <full-sha> --route server --authorization /owned/grant.json
```

The grant is an externally reviewed, narrow authorization to start, **not an
acceptance receipt**. It must be an owner-owned mode600 regular single-link file
with no symlink path components, and exactly:

```
{"generation":"<full-sha>","closure":"<current-32-hex-ID>","route":"server","authorized":true}
```

Initialization creates `candidate.lock` mode600 alongside admission/controller
locks. Legacy state directories missing that lock refuse all commands; there is
no implicit upgrade or reinitialization. Investigate/drain/exclude legacy users
externally before authoring a fresh state directory. Never add a replacement
lock to a running directory or bypass a CLOSED fence with a second OPEN one.

Candidate startup holds controller EX, takes candidate lifetime EX with bounded
wait, checks CLOSED, exact grant/generation/route, refuses any existing candidate
record, drains admission EX and verifies raw hashes. After chdir it exclusively
creates and fsyncs `candidate.json`, then fsyncs the directory. Exact record:

```
{"generation":"<full-sha>","closure":"<current-32-hex-ID>","route":"server",
 "process":{"pid":123,"start":"<Linux stat field22 decimal ticks>","cwd":"/owned/source"}}
```

The process is the guard's own PID before same-PID exec. It releases admission
and controller before exec, retaining only the inheritable candidate lifetime
FD. A concurrent close can publish CLOSED and await lifetime without blocking
startup from finishing. Every importing worker/descendant must retain this FD;
foreground gunicorn must be tested on the actual installed runtime. No per-worker
module attestation is supplied. Non-Linux candidate startup explicitly refuses;
ordinary POSIX launch/close mechanics remain available, but this stricter reopen
protocol requires Linux candidate identity.

Reopen takes admission EX independently of the live candidate. In addition to
the receipt checks below it requires a mode600 exact candidate record bound to
the current closure/generation/server route, receipt process equality, live
`/proc/<pid>/stat` field22 and cwd equality, and a still-contended candidate lock.
A zombie, missing/dead/forged master, missing record or free lifetime lock cannot
reopen. Identity is rechecked after contention; this is a point-in-time check,
not a promise the process cannot die immediately afterwards. Start ticks are
not boot-global identities: never reuse retained state across boots without
external exclusion and a fresh close/grant/acceptance cycle.

Close first durably rotates CLOSED, then drains **both** locks. Only after full
drain may it remove the exact validated own-generation `candidate.json` and
fsync the directory. Malformed/unsafe records are retained and refuse cleanup.
Timeout or interruption leaves CLOSED and preserves the record. A dead/failed
exec candidate is not retried over its stale record: full close must drain and
retire it, rotating the closure and invalidating prior grants/receipts. There is
no killing, automatic receipt creation, source restore, temporary-open,
finally-open, automatic rollback or restore command.

## Reopening and external acceptance

Reopen is explicit, serialized, exclusively locked, and requires matching raw
source hashes plus a mode600 external JSON receipt with exactly:

```
{
  "generation": "<full-sha>",
  "closure": "<32-hex closure ID from status>",
  "source_home": "/owned/source",
  "hashes": {"<each schema-specific relative path>": "<raw-sha256>"},
  "schema": 19,
  "accepted": true,
  "process": {"pid": 123, "start": "<external start identity>", "cwd": "/owned/source"}
}
```

The guard validates receipt structure/binding and the Linux candidate identity
and lock checks above, **not measured acceptance truth or authenticity**.
It does not fabricate/read schema acceptance, probe health, or produce this receipt. A separately reviewed operator acceptance
procedure must measure the manifest's target schema, markers, ready/health, exact fresh accepting
process/start configuration, old-generation retirement and recovery preservation,
then write the receipt. The example's `schema:19` is valid only for a legacy or
explicit19 manifest; explicit20 requires receipt `schema:20` and its exact eight hashes (nine with
`hid-v1`). A20 receipt cannot reopen a19 guard or vice versa, even for the same
source home/generation. Schema18, missing/malformed/mismatched receipts and wrong
hashes/generations refuse reopening. A new close invalidates old receipts via
its closure ID. Receipts are not cryptographic attestations. Authorization to
start is not evidence of acceptance; the external measurement path remains
mandatory.

## Offline acceptance tests

Run only on local Linux/POSIX, with an exclusively NEW absolute synthetic output
path under an already owned task root. No implicit fixture roots, owner env,
configuration, network, SSH, live DB, or application imports are used. Windows
prints UNSUPPORTED and exits2. `-O` refuses before output creation. Grading uses
explicit exceptions rather than assertions.

```
python3 tools/test_surfd_transition_guard.py --out /owned/artifacts/new-fence-run
python3 tools/test_surfd_guard_candidate.py --out /owned/artifacts/new-candidate-run
```

The candidate suite requires Linux and an OWNER.md ancestor. It tests acted
fixed-server exec while CLOSED, grant mismatch/modes/links without application
markers, independent ordinary CLOSED refusals, missing/malformed/dead/forged
candidate identity, live identity without lock, real live reopen, closure
rotation, failed exec retention, full drain timeout, and a forked descendant
retaining the candidate FD after master death. Existing admission tests now
start a real synthetic candidate for acceptance, then stop it to isolate the
ordinary admission lifetime controls. Schema controls additionally exercise legacy19 and explicit19/20 with real live
synthetic candidates, opposite-schema/malformed receipts, exact dependency sets,
missing/mismatched accounts/social bytes at candidate and launch, mismatched
reopen bytes, acted ordinary imports and stale-closure replay. The manifest stays
byte-identical; no upgrade/rebind command is added. These are not real gunicorn controls;
the separately adapted gunicorn harness below starts an authorized live candidate
and authors its clearly synthetic receipt only after a real WSGI response.

Predictions/falsifiers: positive fixed routes create a real module-import witness;
CLOSED/wrong-generation/alternate route/cache attempts must not. An unguarded
bypass must violate that witness oracle. A preclosure writer must hold a real
shared flock, block exclusive drain, then finish its authored write before drain
succeeds. Killing the blocked closer or closing stdin must not reopen admission.
Every subprocess has bounded waits; cleanup kills only exact fixture Popen
handles, never groups or discovered PIDs.

The suite retains JSON command verdicts and logs. It runs controller death and
EOF cuts at simulated pre-install, three-of-six-file install, post-schema-sentinel
change and pre-receipt phases. The fake controller is test-only, not a deployment
capability. It requires the exact parent-created fixture identity/token and canonical
root/home/guard bindings before any close or write. Missing-token and foreign-root
controls prove refusal without state/source mutation. Source/SQLite/cache recovery
sentinels remain preserved, including a
later native row after the cut; repeated guard failures cannot restore stale
bytes. There is no DB restore procedure to approve or exercise. No real P717
migration, scheduler, native HTTP submit, owner-sized drain, recovery
reconciliation, reboot or physical storage/power-loss acceptance is claimed.
Exclusive guard initialization collision is tested; coordinated backup-name
collision handling belongs to the unimplemented recovery driver.

### Real foreground gunicorn lifetime falsifier

`test_surfd_guard_gunicorn.py` separately runs an actual gunicorn master and
one gthread worker/two threads against authored synthetic WSGI, over a private
Unix socket only. It never imports surfd or invokes a live launcher. Supply an
explicit root-local dependency directory: upstream gunicorn23.0.0 + packaging24.2,
or gunicorn20.1.0 + packaging24.2 + setuptools65.5.1 (for pkg_resources). The test
installs nothing, hashes the dependency sources and checks their import roots.
These upstream pins do **not** identify or reproduce distro-patched host bytes.
The explicit `--host-distro` mode instead requires the actual system interpreter,
`/usr/lib/python3/dist-packages`, root-owned nonwritable gunicorn/package source,
an exact declared gunicorn version, and `dpkg-query` provenance. It records the
actual installed bytes/version, not an upstream-equivalence claim.

```
python3 tools/test_surfd_guard_gunicorn.py --out /owned/new-gunicorn-run --gunicorn-path /owned/deps
python3 tools/test_surfd_guard_gunicorn.py --out /owned/new-gunicorn20-run --gunicorn-path /owned/deps20 --gunicorn-version 20.1.0
/usr/bin/python3 tools/test_surfd_guard_gunicorn.py --out /owned/new-distro-run --gunicorn-path /usr/lib/python3/dist-packages --gunicorn-version 20.1.0 --host-distro
```

Predictions and discriminating controls:

- A served authored response and import witness identify the actual worker.
  Both master and worker retain the exact candidate-lock device/inode; an
  independent exclusive flock must contend.
- Closing publishes CLOSED but times out while that admitted master lives.
  A fresh guarded launch refuses without a new import. HUP and deterministic
  max-requests4/jitter0 recycling **still import and serve while CLOSED** under
  the already admitted master, and retain the lock. This is expected: CLOSED
  stops new admissions, not existing-generation descendants. Installation must
  wait for successful drain, never just the CLOSED status line.
- A held request survives graceful master TERM. Its authored completion and
  response, master exit, worker reaping and socket removal must precede
  successful drain. All waits are bounded; cleanup only signals the exact
  parent-created master after checking its start identity, never process groups
  or discovered PIDs. Cleanup failure retains identities rather than escalating.
- A test-only launcher deliberately drops the inherited candidate FD. Reopen
  must refuse; the same lifetime oracle must fail while real WSGI still serves and exclusive drain
  succeeds. This proves why uncooperative/detached routes cannot be approved by
  a passing foreground test.

Linux, nonoptimized Python, link-free canonical NEW output and an owned ancestor
are required before fixture creation. Provenance, guard commands, WSGI events,
responses, lock oracles, logs and cleanup identities remain under that output.
No production gthread4/max-requests5000/jitter500, detached run.sh, scheduler,
service-manager, product schema acceptance, generation handover or live no-loss
proof is implied.

### Legacy direct-import entrypoints

`surfd_import_dispatch.py` renders pinned stdlib-only wrappers for the six legacy
module paths. Each wrapper verifies the dispatch helper bytes; the dispatcher
verifies the guard bytes, acquires an ordinary shared admission lock through an
O_RDONLY descriptor (compatible with a read-only source/service sandbox), checks
OPEN, the fixed generation and all schema/profile-specific source hashes (six
for19, eight for20 or nine for20/hid-v1), then executes the genuine
immutable source in the original module namespace. Its real source origin and
`sys.modules` identity are preserved. Already loaded local dependencies from
outside that runtime are refused rather than silently evicted.

This gates **application import/effects, not Python interpreter creation or
startup hooks**. It is an alternative for a legacy root-owned direct-gunicorn
unit whose ExecStart cannot be replaced. It requires an externally pinned whole
runtime (unchanged modules/resources as well as the pinned dependency set), a trusted
interpreter/import environment and a complete old-process drain before wrapper
installation. A direct import of the immutable files can bypass cooperation;
this is not a sandbox against the same-UID operator or application code.

```
python3 tools/test_surfd_import_dispatch.py --out /owned/new-dispatch-run
```

The suite also proves explicit19 and explicit20 imports through those same six
entrypoint wrappers, genuine synthetic accounts/social origins, missing/mismatched
dependency refusal before application effects, and schema20 CLOSED refusal.
`accounts.py`/`social.py` are pinned dependencies, not new wrapper entrypoints.

The suite installs the exact generated wrapper bytes and acts on module/script
origins, all six targets, O_RDONLY/inheritable FD lifetime through fork, close
timeout, stale dependencies and changed source/helper/generation refusals. OPEN
in this fixture is explicitly synthetic, not a real schema acceptance receipt.
`test_surfd_dispatch_gunicorn.py` separately exercises actual gunicorn legacy
worker imports through those exact generated bytes. A real synthetic candidate
earns an explicitly synthetic receipt, exits while OPEN, then an unguarded legacy
master loads `surfd:app` through the wrapper. Only its admitted worker holds the
O_RDONLY lifetime. Held requests complete while CLOSED replacement workers fail
before real source import; separate HUP, max-requests and fresh-master arms prove
the distinction. A real WSGI FD-drop negative still serves and must fail the
independent lifetime oracle. No product module or DB is imported.

```
/usr/bin/python3 tools/test_surfd_dispatch_gunicorn.py --out /owned/new-legacy-distro --gunicorn-path /usr/lib/python3/dist-packages --gunicorn-version 20.1.0 --host-distro
```

Upstream and actual installed distro provenance remain distinct. Neither this
synthetic test nor its successful cleanup proves actual service configuration,
whole-runtime compatibility, schema acceptance or native-submit no-loss.

## Launch inventory preparation (not enforcement)

Do not equate a finite source search with complete host launch coverage. Before
proposing a transition, reconcile these **source-defined** families with actual
installed definitions and process/start identities:

| Family | Source leads |
| --- | --- |
| Detached master and worker recycling | `surfd/run.sh`, gunicorn HUP and max-requests |
| Boot/restart/reload | `surfd/surfd.service`, loaded fragments/drop-ins and triggers |
| Scheduled/manual KSF import | `surfd/ksfimport.py`, `ksfgrab.py`, all cache/home overrides |
| Other scheduled/manual app importers | sweep, momwatch/momgrab/momboards/momdates/momindex, mapwatch, steamsync |
| Descendant importers | momwatch launching momboards; parent supervision and FD lifetime |
| Deploy/repair/restart tools | `tools/surfd-deploy.ps1`, `surfd/stop.sh`, alternate wrappers |
| Direct Python/WSGI and smoke/test tools | module-scope surfd migrate, operator and automation entrypoints |

With explicit inventory approval, collect bounded process/launcher metadata,
resolved interpreter/source paths and hashes, loaded service and scheduler states,
restart triggers, owning user and path metadata only. Include both snapshot
boundaries to expose churn. Do not probe importer `--help`: app import can precede
argument parsing. Do not read secrets/environment values, logs, DB/cache contents,
player files, shell history or arbitrary job bodies; do not acquire locks, signal,
import, change services or make application HTTP requests. Keep raw inventories
private and publish only sanitized classifications and explicit inaccessible-user,
alternate-path and manual-launch unknowns. Historical service headers conflict;
only observed installed state can reconcile them. An inactive but enabled service
is still a future launch route. Inventory approval is not permission to enforce
exclusion, install source, migrate or reopen.
