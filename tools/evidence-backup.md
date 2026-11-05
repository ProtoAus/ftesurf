# Private off-box evidence copies (operator tooling)

`evidence-backup.ps1` copies **existing** Pi `data/runs` and `data/evidence`
files to a private Windows archive using standard rsync. `evidence_index.py`
produces bounded, read-only per-file SHA256 observations over existing SSH.
Neither changes game capture, verdict fields, rankings, the database or Pi files.
This tooling is not a native/QC patch and does not restart games or the backend.

## Preservation contract

- A new destination gets its `OWNER.md` **before** data. Its protected Windows
  DACL allows only the owner SID and SYSTEM; configuration and payload are checked.
  Existing `logs`, `current` and `history` roots, ancestors within the archive and
  subtrees are checked for reparses/private ACLs before transport. New directory
  components are checked before content; historical payload privacy is checked too.
  Never place the archive in a web-served/public/shared directory.
- Source directories are exactly `runs` and `evidence`, not the whole install,
  player-key directory, map library or dependency cache. The source index opens
  regular single-link files with nofollow/nonblocking openat traversal. Aliases,
  unreadable/changed files and exhausted allowances are explicit, not green.
- No `--delete`, `--inplace`, reverse sync or Pi repair. Existing off-box versions
  move into `history/<transaction>/<scope>` before a changed copy replaces them.
  A file no longer observed on the Pi is retained, not deleted off-box.
- SHA256 independently checks copied bytes against the per-file source index;
  rsync's transfer checksum alone is not the integrity receipt. Zero-length files
  are valid. Same-size edits with restored mtime are compared, not skipped.
- Source index observations and `latest.json`/private transaction logs are not a
  coherent global instant, physical-input attestation, intent, or guilt. Partial
  and late files legitimately change. A dishonest source host can serve clean
  shadows; a compromised archive host can change its own copies. Those ceilings
  are not solved by copying or checksums. Historical unknowns are not rebound.
- No automatic pruning or restore. Low space aborts rather than deleting evidence.
  Pi repair needs an approved immutable-file/repair policy and separate authority;
  never overwrite a potentially legitimate late arrival merely because it differs.

## Runtime and private configuration

Requires PowerShell 7, existing MSYS runtime/SSH, Python 3 on the Pi, and rsync on
both endpoints. Keep rsync and SSH on the **same MSYS runtime**. Native Windows
SSH can pass a text smoke but cannot be assumed to interoperate with MSYS rsync's
inherited descriptors; mixing Git's separate MSYS SSH can fail `dup()` as well.
Use the existing identity and known-host files explicitly; never copy keys or
bypass host-key verification. Effective native-profile paths can contain Windows
backslashes: POSIX `shlex` removes them. Resolve them with Windows path semantics.
Disable MSYS argument conversion for this process only, not the owner's environment.

A verified portable rsync executable plus missing DLLs can use the existing MSYS
runtime without installing/upgrading global packages. Keep signed-package and
licence provenance privately. Do not publish tool binaries, keys or configuration.
If inspecting imports, prepend the actual portable/MSYS lookup paths: a default
Git PATH can report the wrong runtime. Import output can mix `C:/` and `\\`.
Pin the exact required helper/executable/shared-DLL bytes, not an unrelated SDK.
No claim is made to freeze Windows itself or to audit third-party native code.

The private `<archive>/config.json` contains:

| Key | Meaning |
| --- | --- |
| `Version` | `1` |
| `Destination` | Canonical private local directory below `C:\FTESurf-private` |
| `OwnerSid`, `OwnerMarker` | Current Windows SID and this archive's ownership marker |
| `Host` | Existing SSH `user@host`; no passwords or key material |
| `Synthetic` | False for live source; true only for owned agent-work fixtures |
| `Source` | Live `/srv/nvme/ftesurf-server/game/ftesurf/data` |
| `Script`, `Indexer` | Inspected installed paths to these two source files |
| `Rsync`, `MsysBin` | Verified executable and existing compatible MSYS directory |
| `SshArgv` | Same-runtime SSH argv with existing strict trust/identity references |
| `Artifacts` | Array of `{Path,Sha256}` for both sources and required executables/DLLs |
| `TimeoutSeconds` | Positive per-child observer allowance, at most 1800 seconds |
| `MaxFiles`, `MaxBytes` | Positive copy-index entry/read allowances; at most 100000 entries |
| `BandwidthKiB`, `ReserveBytes` | Explicit copy bandwidth and free-space reserve |
| `TaskName` | `FTESurf-EvidenceBackup` or a uniquely owned alphanumeric suffix |

These are operator copying allowances, **not** detector thresholds or recording
limits. Index deadlines/entry/read checks are cooperative, not hard global
CPU/RSS/IO guarantees. One local child clock covers asynchronous stdin delivery,
process waiting and output-copy waiting, including pipe backpressure. Cleanup kills
only its owned process handle on failure; never search/kill arbitrary process IDs
or another session's tree. This is not a hard kernel/disk or remote-process bound.

Verify configuration privacy, actual DLL origins and hashes, plus a small acting
copy/old-version/ACL control **before** copying real data. Artifact mismatch fails
closed. A legitimate toolchain update invalidates affected pins: revalidate at the
real boundary, never silently refresh hashes to make a failed run green.

## Invocations and scheduling

From PowerShell 7, using only the private config **path** in arguments:

```powershell
pwsh -NoProfile -File C:\FTESurf\tools\evidence-backup.ps1 -Config <private-config> -Probe
pwsh -NoProfile -File C:\FTESurf\tools\evidence-backup.ps1 -Config <private-config>
```

`-Probe` proves existing noninteractive SSH acted but copies no evidence. An actual
copy writes private transaction logs and a complete/partial observation. Raw rsync
filenames, hashes, account identifiers and source content must not be exported.
Only counts/status belong in normal operator progress. A persistent empty
`.writer.lock` uses Windows FileShare.None; do not unlink it at release.

After review/install and sufficient Windows task-creation rights, the **same owner**
can register one task:

```powershell
pwsh -NoProfile -File C:\FTESurf\tools\evidence-backup.ps1 -Config <private-config> -Register
```

This registers limited-user **S4U**, no stored password, hourly repetition,
StartWhenAvailable, no overlapping instances, a 45-minute task limit and **no
WakeToRun**. It needs an awake/available archive PC; no always-on guarantee is
claimed. Test the actual scheduled identity/SSH/file/ACL result before declaring
unattended operation. Do not silently substitute a login-only timer or SYSTEM.
An existing task is an ownership conflict, not permission to replace it. An
Access-denied registration requires the owner's Windows admin/UAC step, not a
password request, credential change, host-key bypass or another wrapper chain.

## Qualified scope and current limits

Source controls: actual POSIX nine tests/zero failures/skips cover real read,
unchanged source identity/bytes, zero file, same-size/restored-mtime edit,
symlink/hardlink/FIFO, concurrent mutation, unreadable subtree, byte/entry/deadline
allowances and alias/escape refusal. Every negative has acting ordinary controls.
Actual Windows/MSYS/SSH whole-entrypoint controls copy late arrivals, retain both
old edited versions and removed-source copies, verify private payload ACLs and
full SHA256, reject mismatched artifacts/real share contention before transport,
and observe an acting child timeout without advancing the last completed copy.
The timeout's source actor is later checked by PID **and birth**, not blindly killed.
The review-fixed source separately rejects junctions at all three managed roots and
an unexpected grant on an empty log parent before transport/diagnostics. An owned
local actor never reads a 4MiB stdin body, emits a witness and sleeps for 120 seconds;
the wrapper returns in about three seconds, the exact actor is already gone and
the writer lease is reacquired. This proves the exercised backpressure boundary,
not hard global IO or remote cancellation. Final-source ordinary input/zero arrival,
same-size restored-mtime edits, exact record/partial history and removed-source
retention also acted (eight observed files, ten retained, 26 bound artifacts).
Original transport/literal/path/pin-capture failures remain diagnostic history,
not feature passes. No numerical detector-performance claim follows from these.

**Before first real-data use:** the first two whole-feature reviews blocked on
managed-directory checks and synchronous stdin outside the deadline. Both seams
are fixed and their synthetic falsifiers acted; renewed whole-feature review,
publication, a real-data first copy and scheduled acceptance remain pending. A least-
privilege fixture S4U registration was refused with Access denied; an exact task
query proved no task remained. Standalone copying is independent of that OS
permission. This is preservation tooling, not completion of an anti-cheat plan.
