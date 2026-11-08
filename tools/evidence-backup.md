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
  regular single-link files with nofollow/nonblocking openat traversal by default.
  Optional `StageStore` admits only the existing P395 stage-retention pair:
  `evidence/<map>/<leaf>.rec`, exactly two links, and a second nofollow descriptor
  at the identical map/leaf in the declared backend store. Both descriptors must
  match device/inode/link-count/size/mtime/ctime before and after hashing. Arbitrary,
  third, run-directory and unbound links remain deferred. This observes existing
  bytes, not exclusive ownership, a verdict or authority to unlink either name.
  Unreadable/changed files and exhausted allowances are explicit, not green.
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
| `StageStore` | Optional explicit `/srv/nvme/surfd/data/evidence`; otherwise hardlinks remain deferred. Synthetic scope only permits the owned source sibling `kept/evidence`. |
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

Source controls: actual POSIX fifteen tests/zero failures/skips cover real read,
unchanged source identity/bytes, zero file, same-size/restored-mtime edit,
symlink/hardlink/FIFO, concurrent mutation, unreadable subtree, byte/entry/deadline
allowances and alias/escape refusal. Six added cases cover the explained stage
pair/default refusal, missing/wrong inode, third link, wrong scope, store aliases
and an acting mutation through the retained alias. Every negative has acting
ordinary controls. The Windows whole entrypoint also exercised default refusal,
explicit pair/ordinary/zero success, an alias edit with restored mtime and exact
old-stage history, and wrong-namespace refusal before transport (nine source,
eleven retained, one explained pair, 26 pins).
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

**Real-data boundary:** two renewed whole-feature reviews cleared the directory/
stdin fixes, and that tooling was published. The first actual copy retained 7,535
files; 7,422 passed independent SHA/length checks, but 113 regular two-link files
were explicitly deferred, so that historical transaction is NOT a complete pass.
Metadata-only investigation found all 113 paired with the existing canonical
backend stage store, consistent with P395's documented retention behavior. The
narrow optional `StageStore` compatibility was then independently cleared by two
whole-feature reviews and published as `410063dd`. Exact installed source and 26
artifact pins passed a new actual observation at 2026-11-05 21:32:00 UTC: all
7,535 files / 2,095,635,847 bytes independently length/SHA verified, including
113 explained stage pairs; zero deferrals or pending mismatches, both rsync exits
zero. The original partial observation and previous code/configuration remain
retained. No link was removed or arbitrary-hardlink gate relaxed. This is a
per-file copy observation, not a coherent global instant or hostile-host proof.

**Historical scheduled acceptance completed on 6 November 2026.** The owner
completed normal UAC registration at 02:17 UTC; the actual same-owner limited-S4U
run at 02:18 returned zero and produced a new complete observation at 02:20:04 UTC:
7,535 files / 2,095,635,847 bytes, zero pending/deferred, both rsync exits zero and
the empty writer lease released. The final read-only acceptance at 02:55 UTC
verified the exact configured action, S4U/limited owner, matching artifacts and
observation after scheduled start. The earlier 02:54 observer did **not** establish
exact-action/new-observation acceptance; that incomplete check and the original
Access-denied/no-task fixture remain retained, not relabelled as passes.

Do **not** register or run the task again merely because an older handoff says
pending. This is reused historical acceptance, not a fresh claim about today's
task or an always-on service. The archive PC must still be available; immutable
source repair/restore and pruning require separate approved policy. This remains
preservation tooling, not completion of an anti-cheat plan.
