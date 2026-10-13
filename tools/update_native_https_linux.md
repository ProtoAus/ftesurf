# Linux default-HTTPS native/menu acceptance — 2026-10-13

## Scope and result

**The Linux default production-HTTPS check/menu/restart gate passed.** This is
native source/test acceptance, not a new engine patch, deployment or release.
The published 0.1.25 archive/feed/bootstrap remain byte-exact P687 artifacts.
External initiating engine: accepted P692 source195dc58e9054b421dc9c76530a0715df64864183;
QC baseline2221a3c4014feaaa5a443529459fe22ddfef250d. Initiator and archived
returning game have deliberately different provenance.

Driver: `tools/test_update_default_https_posix.py`; client-free falsifiers:
`tools/test_update_default_https_posix_unit.py`. Inputs are public signed-feed,
archive and release receipt bytes; neither script reads a signing key.

Retained owner/evidence root:
`C:/FTESurf-worktrees/lhttps-20261013T154800Z/`.
Final-byte native PASS: `artifacts/acceptance-03/result.json`,
2026-10-13T16:13:00.253242Z–16:16:23.309862Z. Independent re-review:
`artifacts/review-linux-https-02.md`, **OK with notes**, all four first-review
blockers resolved. Parent inspected all five final screenshots, not only logs.

| Frozen input | SHA256 |
|---|---|
| Driver | `cc2fbc40231ff5cfa54dfdddbd0ae02b59fa916138d5d548d25d167a7071ec16` |
| Unit controls | `ae27145bc422350389f7a97748e2c6069e4b299eea27f63e7a11a05881d544ae` |
| Retained namespace wrapper | `f8745d2de34c520ce5004b513e8cd73707597d5f76b8896841fa0dd929b78c0d` |
| External P692 initiator | `581272077634dbbf4e27a58f3a4a1ffb0f272b772a0a04a508a0b6a4a66b36a1` |
| Production Linux archive | `039e9bce31b6563305e7ae7f8e8c9edd8b16faa69b57d9bd959d8c9e8baa6aef` |
| Real archived Rust launcher | `c5d6fa7828191b798a674553141e7f71f2881215c6b115abee4abcddfbf1518c` |
| Real archived returning game | `12d40c853fd590a5a83bcd201ff97bf9cd3b8183c82b58b1588e7e17886800b6` |
| Default HTTPS signed envelope | `1568a34c99ffca799db6ddb70dee9fde941d38038f7bdff32afbedd99386bb9f` |

## Acted native matrix

- **Consent/current:** actual screen7/client1 starts undecided. Authentic Keep off
  persists `0\n`, gives disabled pane and unchanged ledger; Enable persists `1\n`
  and native signed production check says current0.1.25. No URL/pin/insecure-policy
  override; both default URL and `update_allow_insecure=0` are inspected.
- **Content repair:** only signed `ftesurf/gfx/env/milk.png` is corrupted and its
  ledger row/version stale. Persisted consent on a cold start performs the check;
  native `installed 1 files` occurs before the launcher, restores signed bytes and
  shows Updates/restart. The authentic Restart through launcher button acts.
- **Engine repair:** only archived `ftesurf64` is corrupted with a stale ledger.
  External initiating P692 executable is untouched. Native requires the launcher
  and leaves corrupt engine bytes unchanged. The authentic pane/button hands off;
  real Rust restores the signed engine and its execute bits.
- **Both real returns:** complete captured launcher vector is exactly
  `<real-launcher> --dir <owned-install>/ --wait-for-game --yes`; returned vector
  is exactly `<real-ftesurf64> -manifest default.fmf`. Only paths are normalized.
  Returning cfg is an owned saved-settings hook, not injected launcher/engine argv
  and not an adapter. Real new processes print standalone returning actors;
  Updates is screen7/client1, consent1, uptodate, default production URL. Final
  ledger/certificate are0.1.25 and no native journal remains.
- **Protection and closure:** archived launcher/notices, count/raw bytes/critical
  receipt hashes, tar ownership/modes and the whole signed Linux file set bind
  to the unchanged production archive. Settings, recording, edited local zone,
  mounts and mounted-content sentinels remain byte-exact; final signed sweep
  excludes only explicitly protected user-edited paths.

`strace -f -ff -e trace=process` records the full fork/clone/exec/terminal tree,
including very short-lived tasks and orphans. Parent child IDs must resolve to
trace files, exactly one initial root must reach every task, and the real return
must descend through the launcher. Complete initial/launcher/return vectors are
checked. Raw task exits and group/private-namespace census are saved BEFORE any
success grading or containment. Final matrix: **53/126/126 tasks**, **52/125/125
creation edges**, every task and all three tracers exit0. Seven real executable
actors; no exceptions for product/nonproduct nonzero exits. Every pre-cleanup
group and unexpected-namespace census is empty.

## Controls, failures and preservation

`artifacts/units-04.log`: **15 final-byte tests OK** (review also inspected the
passing units02 run), including extra/reordered argv,
missing/nonzero exits, omitted referenced task file, wrong launcher ancestry,
resumed task creation, screen0/client2/noncurrent returns, echoed-command marker
collision, real fast orphan execs and a reaped leader with a surviving group.
Real traced withheld-marker/forced-wait failures save pre-containment snapshots
and every referenced final terminal outcome. The tracer remains alive while its
owned tracees terminate; failed attempts are never rescued by containment.
Static export-root, ancestor and sentinel links reject before referent reads or
copies. Real tmpfs export/retirement failure controls preserve a verified persistent
non-secret recovery tar, retain FAIL and verify the tar after source removal.

Before ordinary export/retirement, the independent recovery bundle includes only
allowlisted cfg/log/screenshots/updater metadata/protected sentinels. It excludes
identity.pfx and mounted-content exports. Its inventory, regular member ownership/
modes and per-file size/hash are independently verified. Wrapper refuses to end
an unretired runtime namespace if this verification fails: retain its explicitly
owned host unshare PID/namespace for recovery; a marker alone cannot discard it.
**That recovery-blocked wrapper branch is source-reviewed, not fault-injected.**
Export and retirement failure branches themselves are acted by the tmpfs controls.

Attempt01 remains **FAIL**, despite complete consent/content partial arms: POSIX
console input echoes contain future output markers. Exact standalone timestamped
echo lines, not substring checks, now gate completion. Attempt02 passed all native
arms before review but is **pre-review evidence only**: omitted-file census,
early-failure snapshots, linked export roots and ephemeral failed recovery were
four reviewed harness defects. Only attempt03 is final frozen-byte acceptance.

## Environment and exact accepted commands

Ubuntu22.04/Python3.10.12/strace5.16 on WSL2 kernel6.18.33.2, private PID/mount
namespaces, private tmpfs runtime and `/tmp`, private Xvfb:91/software OpenGL,
owned HOME, no Wayland/shared GUI socket. The standalone driver requires that
owned runner contract. Retained wrapper's input paths point to read-only accepted
P692 binary and production archive/feed/receipt in their previous owner roots.

```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-22.04 -u root --exec bash \
 /mnt/c/FTESurf-worktrees/lhttps-20261013T154800Z/artifacts/run-unit-posix.sh 04 \
 > units-04-stdout.log 2> units-04.log
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-22.04 -u root --exec bash \
 /mnt/c/FTESurf-worktrees/lhttps-20261013T154800Z/artifacts/run-linux-https.sh 03
```

These exact attempt paths already exist: do not overwrite/reuse them. For a new
session make its own OWNER/task root and redirect the wrapper/runtime/evidence
there; previous roots are immutable inputs, not cleanup targets. No full install,
compiler/dependency cache, original player data or production settings were copied.
Final runtime is explicitly inventoried/retired after evidence export and process
completion. Small source/trace/PNG/recovery evidence is retained under the owner.
Windows grader regression:13 tests OK; signed-feed regression:12 tests OK.
No product source, compiler flags, ship-set, release pins or deployed binary changed.

## Limits and remaining work

- Keep off proves permission/disk/ledger state, NOT production zero-request counts;
  existing counted loopback controls are separate.
- Repair/stale-ledger arms at the same signed0.1.25 version, not publication of a
  newer version, CDN/TLS-outage retry acceptance, or a release-builder operation.
- Synthetic trusted console menu callbacks and Xvfb pixels are not physical-input,
  gameplay, Linux glibc-floor/hardware support or human UI acceptance.
- Process interruption is not power-loss durability. P692 flush ordering,
  Windows process-interruption/deferred-live-journal fault injection and bounded
  safe postcommit object cleanup remain separate backlog items. No hostile
  ancestor-swap/hardlink guarantee follows from static export-link controls.
- Canonical Windows installs, lobbies, public objects/feed/key and version0.1.25
  remain untouched. Linux HTTPS acceptance does not deploy P692 or certify peers.
