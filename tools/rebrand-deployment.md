# World of Surf presentation deployment — 2026-10-14 UTC

The operator approved the P705/P710 design and deployment on 2026-10-14.
This is a development-fleet presentation rollout, **not a Build NN, release,
archive rename, new signed feed, account identity migration or data migration**.

## Inspected source and game deployment

- Exact clean product commit: `80618e52e50bff713ad6b645511308c00d4c0ccd`
  (P710, including its already-published dependencies). Later peer commits are
  not part of this build. Engine ledger inspected at `886f302`; the native
  engine/plugin binaries were not rebuilt or replaced.
- Owned evidence root:
  `C:\FTESurf-worktrees\rebrand4-20261014T1710Z\artifacts`.
  The canonical checkout's dirty map configurations and peer source were not
  used, reverted, staged or shipped.
- `pwsh -NoProfile -File src/build.ps1 -Jobs 8 -Pi` from the clean worktree
  compiled all three VMs with zero warnings, uploaded the qw/cs pair and
  restarted **all 12 discovered active instances**, with a fresh empty-player
  check before each restart. Completed at about 17:20Z. Both server `.prev`
  predecessors remain available. An earlier captured build failed to record its
  log because the artifact directory did not yet exist; the final build/deploy
  log is complete (`fleet-deploy.log`).
- Before that restart, all 13 lobby configs (the compatibility default plus
  lobby1..12) were checked against the exact source: every non-hostname byte
  matched after CRLF normalization. Only the hostname presentation changed.
  Backups and per-file before/after hashes are retained outside the served tree
  at `/srv/nvme/agent-work/rebrand4-01a13b5b-fleet/before/`.
- At **17:23:16Z**, all three VMs and `default.fmf` were deployed and
  hash-verified in **both** `C:\FTESurf` and `C:\FTEQuake`. The 13 existing
  optional lobby configs were updated in the first install; absent optional
  lobby configs were not invented in the second. Each replaced Windows file
  has a `.pre-rebrand4` rollback sibling. Protected preferences, default config,
  executable and plugin hashes observed at preflight stayed identical.

| Initial P710 product (17:23Z) | SHA256 at both Windows destinations |
|---|---|
| `qwprogs.dat` | `39c5c945457003fd5b32cfe214baed3df23786249e9b833bf197d694e755f3cf` |
| `csprogs.dat` | `b5dd849d17041287da7f09f18c8f00556e15fe5404e859be827207b88c0baacc` |
| `menu.dat` | `373193f51f56869e80a0d16024cdfbfb9e49103423af44e54b2906272fd28847` |
| `default.fmf` | `9cfb40ee3ed7bf2d1b828f4e2136f7be22c9bb686c8cf4a24505ee62b8ab8e0a` |

### Combined client after concurrent trainer delivery

A concurrent P712 client-only rollout at 17:38/17:40Z used the earlier
presentation-withheld policy. It preserved the new menu/server/configs but
replaced CSQC with `f30264e...`, reverting the client labels. The operator's
current approval supersedes that policy; **the trainer was preserved, not
rolled back**.

- Clean, public delivery snapshot:
  `0303a987f0120159c8707ae25e16f930ba31009c`, branch
  `agent/rebrand4-approved-presentation-trainer-delivery`.
  It is P710 plus the exact two P712 client files from the peer's inspected
  `d643b8a` delivery, its test and Patch 712 metadata. No P711 functionality,
  new patch number, engine pin/tag, QC Build or main-branch reversal.
- `build.ps1 -Jobs 8 -NoDeploy`: all VMs, zero warnings. The actual compiler
  output is the documented owned `rig/build-nodeploy-*` directory, **not**
  `ftesurf/`; the initial harness's wrong artifact lookup was retained and
  corrected before the subject arm ran.
- With the **actual installed P710 SSQC/menu**, the real dedicated-socket
  synthetic trainer control loads all fixtures but remains hidden. The combined
  subject passes native/Momentum/KSF-v2/v3, missing-input abstention, 2,100-sample
  catchup, pause/.25x/4x/back-seek/off-on identity and replay-close reset. Inspected
  pixels show both `World of Surf` and the demo trainer. The trainer/watch source
  files are byte-identical to `d643b8a`; only the other approved presentation
  files differ from that delivery.
- At **18:10:00Z**, only CSQC was replaced on the fleet. Twelve positively empty
  active instances restarted, each with a changed nonzero PID and active state.
  At **18:10:53Z**, both Windows installs matched the same combined client hash.
  Server/menu/config/native/preference hashes stayed unchanged. The peer's
  predecessor and former `.prev` are retained; no owner process was terminated.
- **Current combined CSQC SHA256**:
  `af01a4eb20f16ad2149bf26309c188b75fe43dfaffd4f370019299ab9d556dae`.
  A fresh unseeded live client downloaded `5ad4843a.dat` with that exact hash,
  drew the board/new HUD, captured a screenshot and reached the marker with
  zero QC errors. Earlier `b5dd849d...` live witnesses below remain historical.

## Acting controls and observed limits

- Frozen source audits: `test_product_brand.py` 6 tests,
  `test_package_brand.py` 5 tests, `test_rebrand.py` 7 tests pass.
- **Old vs new pixels:** an owned process using the saved predeployment menu
  drew `FTESURF`; the same fixture using the built menu drew `WORLD OF SURF`.
  The flat and milk/station layouts, consent and 1.5x UI scale were photographed
  at actual 1280x720; a separate narrow arm was actual 800x600.
- Harness failures are retained, not passes: first menu commands ran before
  initialization; subsequent attempts revealed forced consent/update prompts,
  maximized-window sizing and Win32 DPI virtualization. Final `menu6` uses
  explicit offline synthetic-fixture consent, post-init commands, DPI-aware
  resizing of only its own process, and captures actual image dimensions. It
  never accepts or edits the owner's consent/preferences. Early wrong size
  images are not evidence of the requested resolutions.
- **Known pre-existing limitation confirmed:** `screen_terms` at 800x600 still
  has body text hidden beneath its fixed button strip, with no scroll. This is
  already recorded in BACKLOG's Patch 647 Steam-offer/terms entry; the new
  screenshot is not a narrow-consent acceptance pass. At 1280x720 the full
  disclosure fits. No unrelated layout fix is claimed here.
- All twelve live heartbeat names became `World of Surf -- ...`; no player
  records or technical lobby keys were renamed.
- A fresh unseeded client joined `192.168.1.102:27510`, downloaded
  `downloads/csprogsvers/9cefe0ea.dat` with the exact deployed CSQC hash,
  received the new server welcome, drew the Local board (`cols 8 type 14`),
  captured a screenshot showing the new HUD title, and reached `PISMOKE DONE`
  with no QC errors. `tools/pi_lobby_smoke.py`: zero failures.
- A second fresh client with the native plugin and opt-in requested downloaded
  the same CSQC and drew the Online shell with **WOS**, reaching its marker and
  zero QC errors. Its online fixture had **not** accepted online terms, so the
  table correctly refused data and remained the legacy fallback. This is
  **not** native-table renderer acceptance; no claim is made about native rows,
  linked-account browser round trips or automatic-update failure dialogs.

## Web presentation deployed without release

### Board and account pages — 17:36:10Z

Exactly `accounts.py`, `web/board.html`, `web/board.css` and `web/board.js` from
`80618e5` were hash-guarded, backed up and installed. The full JS delta is display
strings only. Six account AST changes are presentation strings; routes, realm,
configured callback, STATEMENT and signed token grammar are unchanged. No
`surfd.py`, functional P706 module, environment, cron or schema was replaced.
Baseline accounts/web/surfd controls pass; 67 named staged live-matched suites
pass across the main and confirmed tail receipts, plus seven brand tests.
`test_ksfgrab` is excluded because that functional module is absent live;
`test_momindex` requires a real import corpus and is not an offline unit suite.
These are not claims that the whole exact-target backend was deployed.

Initial failures are retained: live tests pinned schema 16 while live runtime
already had 17; stage templates were omitted; and optional/test-only fixture
imports/layout were incomplete. Exact-commit tests and complete secretless staged
fixtures repaired only the harness, never the live backend. Installed AST and
route controls prove new display without provider/session/auth identity changes.
The master was positively attested by UID/cwd/parent/app/listen socket/unique
worker relation and start time (this installation has no `gunicorn: master`
setproctitle). Graceful HUP actually replaced the worker and produced readiness.

The child timed out before returning its final report. Its completed deployment,
reload and HTTP receipts were inspected; the parent independently rechecked
four exact destination hashes, unchanged `surfd.py`, public board bytes/MIME,
new link copy, a real wrong-request 400, no-store and no cookies. No swap/HUP was
repeated. Full Steam/provider round-trip and native-browser rendering remain
human/operational gates.

### Landing page — verified by 17:49:45Z

New tooling commit `90d2566bf48544af8d606273f75fd409633b5c35` adds a **separate**
`src/release/present.py`/tests/contract. Twenty-six native Linux synthetic controls
pass on the committed source; independent review found no blocker within the
quiescent-stage/cooperating-writer contract. `publish.sh` and signed-release
behavior are untouched. See `src/release/present.md` for limits, including no
power-loss/fsync guarantee and no automatic content sanitization.

The exact public 0.1.25 receipt rendered the P710 template into a fresh owned
output with `sitepage.ps1 -DryRun`. A lock-captured complete old-tree copy then
received **only nine reviewed public presentation files**. Dry-run hashes matched
all nine rendered files before the separate tool atomically advertised
`presentations/brand-20261014T1750Z`. Old `releases/0.1.25` still matches its entire
original file manifest. **All 20 live `/ftesurf/` files** match expected hashes and
MIME types, including the new favicon/wordmark/OG/touch icons. Site and board
missing-file controls return real 404s.

Protected SHA256, unchanged in disk and actual public responses:

| File | SHA256 |
|---|---|
| `version.json` | `12cf135078c539116ff3997c36f7db3df50bf5be3eccbeb001eef82c1042b7f3` |
| `update.json` | `1568a34c99ffca799db6ddb70dee9fde941d38038f7bdff32afbedd99386bb9f` |
| `update-verified.json` | `bba875ac610b146be056fd9545c79dc728c1dc2a2dc67a86957438ecd974c4e6` |

No public version/archive/upload/signing/release/pruning operation occurred.
The existing `sitepage.ps1` normal publish path still must not be used to replace
an immutable release; the new tool is the supported presentation transaction.

## Canonical route still blocked on root authentication

Read-only external controls proved `/worldofsurf/` was the unrelated file
browser fallback, not a working new site: missing assets similarly returned
HTML 200. Root nginx installation/testing/reload requires operator
authentication. Existing `/ftesurf/` remains the deployment/compatibility URL;
legacy signed callback realm/base remains unchanged. New-route acceptance
requires authenticated nginx installation followed by body/MIME/404 controls,
not an HTTP-200-only check.

The exact snippet candidate and a hash-guarded operator script are retained at
`/srv/nvme/agent-work/rebrand4-01a13b5b-web/operator/`. The script is syntax-checked,
**not executed or target-host root-verified**:

```sh
sudo sh /srv/nvme/agent-work/rebrand4-01a13b5b-web/operator/nginx-operator.sh
```

It refuses a changed installed/candidate hash, backs up outside nginx includes,
tests before/after the snippet install, reloads only after a clean test and tries
to restore the predecessor on failure. It changes no vhost/backend/service user.
Authenticated operator action and external old/new body/MIME/404, GET/POST/rate
and legacy-callback controls are still required. Two SFTP staging connections
closed; guarded SSH stdin then staged the script and verified its hash/syntax.
A later read-only SSH handshake also aborted; no failed transfer/root probe is
counted as deployment. Never supply credentials in agent command arguments.

## Retention and rollback scope

Only this session's ordinary Windows menu/smoke rigs were retired, after no owned
process remained. Logs, screenshots, harness configs and available per-rig
predeletion inventories are under `artifacts/runtime/`. The first retirement
command timed out after two owned roots had already retired; their logs/images
survive, but only the later roots have complete predeletion inventories. Earlier
rebrand roots were not moved/deleted.

NanoPi mixed-source snapshots/test logs and rollback are retained in the task
roots. About 420 MiB of verified secretless matched/target/tmp fixtures
were retired after all fixture/source links were proven internal and source
provenance preserved. **The private mode-600 predeployment DB backup is retained
in the backend rollback root** (about 1.1 GiB); it is not a schema migration or
public artifact and must not be exported. Operator routing artifacts and static
pointer/manifests remain for recovery; no owned service process is retained.

Coordinate and recheck live players before any rollback restart. Restore the
paired fleet progs from their `.prev` only after verifying they still contain
this rollout's predecessors (another later deployment may own `.prev`). Config
rollback files live in the task-owned NanoPi path above. Windows has uniquely
named `.pre-rebrand4` copies. A rollback restores only these exact recorded
files, not an install, player-data tree or another session's source.
