# POSIX pre-import transition fence (offline preparation only)

This stdlib-only helper is **not a deployment or migration driver**. It never
imports surfd, opens a database/cache, installs source, edits a scheduler, starts
a candidate, or restores anything. P717 live schema18→19 remains blocked on
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

The immutable manifest has exactly these keys:

- `generation`: one lowercase full 40-character SHA.
- `source_home`: one existing canonical source directory, used as application cwd.
- `hashes`: raw SHA256 digests for exactly `surfd.py`, `ksfimport.py`,
  `ksfgrab.py`, `ksfprofile.py`, `tools/ksfconvert.py`, `tools/ksfreplay_info.py`.
- `routes`: nonempty object of explicit route names to **complete fixed argv
  arrays**, starting with an absolute real executable path (resolve interpreter
  symlinks first). No user argv suffix, environment override, alternate cache or
  alternate home is accepted. This is an operator-authored allowlist, not an
  automatically approved production route set. Do not allowlist daemonizing,
  arbitrary `-c`, shell, or secondary unguarded launcher commands.

There is one pinned generation per state directory, no generation-changing or
manifest-update command. This seam does not implement old18→new19 rebinding. The
synthetic old writer means a cooperative writer admitted *before closure*, not a
real schema18 application. Integration must separately review the generation
handover and installation procedure; never create a second OPEN guard to bypass
an existing CLOSED fence.

Initialization always starts CLOSED. Each close serializes against other
controllers, atomically replaces state with CLOSED and a fresh closure ID, fsyncs
file/directory, then attempts bounded exclusive admission-lock acquisition.
Foreground launches acquire a shared lock, check OPEN/generation/route/source
hashes, and exec the fixed application interpreter **in the same PID**, with the
shared FD inherited. Only a fixed minimal environment (`PATH`, `HOME`,
`PYTHONNOUSERSITE`) is supplied. This is intentionally not yet a surfd environment
loader. Closure is durable before drain starts. Timeout, controller death, stdin
EOF, or dropped lock/transport cannot reopen admission. Success says only that
cooperative FD holders drained; it does not inventory arbitrary host processes.
Power-loss durability depends on the filesystem; no physical power-loss test was
performed.

`candidate` is deliberately BLOCKED while general admission remains closed.
There is no temporary-open, finally-open, automatic rollback or restore command.

## Reopening and external acceptance

Reopen is explicit, serialized, exclusively locked, and requires matching raw
source hashes plus a mode600 external JSON receipt with exactly:

```
{
  "generation": "<full-sha>",
  "closure": "<32-hex closure ID from status>",
  "source_home": "/owned/source",
  "hashes": {"<each of the six relative paths>": "<raw-sha256>"},
  "schema": 19,
  "accepted": true,
  "process": {"pid": 123, "start": "<external start identity>", "cwd": "/owned/source"}
}
```

The guard validates receipt structure/binding, **not its truth or authenticity**.
It does not fabricate/read schema or process acceptance, inspect PID identity,
probe health, or produce this receipt. A separately reviewed operator acceptance
procedure must measure schema19, markers, ready/health, exact fresh accepting
process/start configuration, old-generation retirement and recovery preservation,
then write the receipt. Schema18, missing/malformed/mismatched receipts and wrong
hashes/generations refuse reopening. A new close invalidates old receipts via
its closure ID. Receipts are not cryptographic attestations. Reopening this seam
must never be used as a substitute for the missing candidate acceptance path.

## Offline acceptance tests

Run only on local Linux/POSIX, with an exclusively NEW absolute synthetic output
path under an already owned task root. No implicit fixture roots, owner env,
configuration, network, SSH, live DB, or application imports are used. Windows
prints UNSUPPORTED and exits2. `-O` refuses before output creation. Grading uses
explicit exceptions rather than assertions.

```
python3 tools/test_surfd_transition_guard.py --out /owned/artifacts/new-fence-run
```

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
migration, gunicorn, scheduler, native HTTP submit, owner-sized drain, recovery
reconciliation, reboot or physical storage/power-loss acceptance is claimed.
Exclusive guard initialization collision is tested; coordinated backup-name
collision handling belongs to the unimplemented recovery driver.
