# P689 Windows default-HTTPS/menu acceptance — 2026-10-13

This closes the Windows default-HTTPS native check/menu/restart gate. It does not
claim a new product patch, release, feed publication or deployment. Product code,
engine/tag pins and qcbuild are unchanged. Linux default-HTTPS native menu/restart
and native journal replacement crash/rename safety remain separate open gates.

Evidence root: `C:/FTESurf-worktrees/httpsgate-20261013T120300Z/artifacts/`.
Final-byte complete PASS: `acceptance-08/result.json`, harness SHA256
`cb50eed92085b520a7ac07cc10770315f56c1e33a335d3bdc546ebc09855a34e`, UTC
2026-10-13T12:41:00.239Z–12:41:53.630Z. Acceptance06 also passed and was freshly
reviewed; attempts 01–05 and 07 are retained FAIL, never accepted from partial arms.

## Inputs and scope

- QC inspection: `fd992912a805d8deea3817eab5504f69437068df`, clean detached
  before two test drivers/docs were added. Canonical QC/engine peer edits were
  neither built, shipped nor modified.
- Engine inspection: `27c58e07a993636aa6d5f75064174518c8cea5c2` detached clean.
  Its `engine/common/qkupdate.c` is unchanged from P689 source `c325d045...`;
  Git-LF SHA256 `dab0308e0a2442554ffba489da10adfd2ff3c3f898745947a02bebadb7c455e9`.
  The canonical engine's older working file is the Quakers-only updater and is
  not this source. Actual menu source is `src/menu/m_update.qc` (singular).
- Initial real P689 native binary: prior accepted
  `nrecover-20261013T094240Z/build/win-final/release/fteqw64.exe`, SHA256
  `e9e992469ebb622bff68ac55774f83d81f3ca86a8513c102361fef04466f1c49`.
  It runs externally with a synthetic archive basedir; it is not deployed here.
- Exact production Windows `ftesurf-0.1.25.7z`/receipt, SHA256
  `8597d4b330662115dceab13ff042f72185cfb74784ac88384bc7b71825333d60`, from
  `update-20261012T074529Z/rig/coherent-publication-live-04/`. Archive contains
  821 files / 64,443,260 raw bytes. Receipt critical hashes/count/bytes, bootstrap
  notices and full signed Windows file closure are verified before client launch.
- Unmodified archived real Rust bootstrap SHA256
  `338404f5b5590f8a5ef7c0f50b8012a07913bf80dd5065eb1aad2a8f860ea2ed`;
  separate inspected clean source `5c60f697c635a8b82affdcd46f51a50aedd3d280`
  under `update-20261012T074529Z/final-launcher`.
- Returning real archived P687 game SHA256
  `0deac625be660562234e4a16aede160463022fd959bcb7691255bd203f26d348`. It is deliberately the published release,
  not the P689 initiator or a small echo adapter.
- Default `https://proto.bar/ftesurf/update.json`, signed envelope SHA256
  `1568a34c99ffca799db6ddb70dee9fde941d38038f7bdff32afbedd99386bb9f`, version
  `0.1.25`. Fresh HTTPS response must equal the prior verified envelope.
  All rows fit native 32 MiB per-object policy; Windows closure has 820 rows.
  There is no manifest URL, key/pin, policy or insecure transport override and no
  loopback server, bootstrap adapter, game-argv injection or signing-key read.

## Controls, subjects and observed results

| Arm | Acted control/subject | Result |
| --- | --- | --- |
| Consent control | Real Updates pane `client=1 screen=7`, undecided `-1`; authentic Keep updates off click persists `0`, state disabled, ledger unchanged; authentic Enable click persists `1`, native default feed says up-to-date | PASS |
| Content | Only synthetic `ftesurf/gfx/env/milk.png` corrupted; ledger for this row marked stale/version `0.1.24`. Persisted opt-in cold check finds exactly one file, native installs it before handoff, exact signed bytes restored, menu state restart | PASS |
| Engine | Only synthetic archived `ftesurf64.exe` corrupted/stale row. External native initiator stays intact. Native leaves corrupt file untouched and authentic Updates pane says launcher; exact bootstrap repairs it through production HTTPS before launching the real archived game | PASS |

Both restart clicks are authentic `mu_restart` hover/down/up events. The native
fixed launcher vector is fully parsed with Windows `CommandLineToArgvW` and must
be exactly the owned bootstrap plus `--dir <owned root>/. --wait-for-game --yes`.
The returning vector must be exactly its owned archived executable plus
`-manifest default.fmf`; Rust's Win32 extended drive prefix is normalized only in
path fields. Additional flags/game commands/order changes/unexpected executables
are rejected. Ordinary synthetic saved settings load the returning test cfg;
bootstrap arguments/source are untouched. Archived `DISABLEHOMEDIR 1` prevents
owner-home settings writes; `cfg_save_auto 0` protects synthetic player settings.

Returning games must freshly log
`consent=1 state=uptodate screen=7 client=1`, default feed URL and a unique real
return actor. Five individually named screenshots exist; the parent inspected
the restart/launcher/current panes. State and signed offline envelope end at
`0.1.25`; no native journal remains. Final full signed file hash sweep passes
apart from intentionally protected edited zone/mounts. Settings, recording,
edited local zone, local mounts and unrelated mounted-content sentinels survive
byte-for-byte; hashes are in the result.

Each initiator is suspended, assigned to an owned kill-on-close Windows Job,
then resumed. Complete PID/image/argv/exit census is saved before grading:
initiator, archived bootstrap and distinct returning game all exit **0**; job
active count is **0 before cleanup**. Exact Windows System32 `conhost.exe` exit
**109 (ERROR_BROKEN_PIPE)** is separately retained/classified as an OS console
host, not relabelled a product exit0. This narrow amended preregistered contract
rejects nonzero product exits and any other conhost exit; all other captured
executables must belong to the expected chain. No owner/peer process is killed.

## Reproduction and falsifiers

From the owned QC worktree on Windows, with the exact verified paths above:

```text
python -B tools/test_update_default_https.py \
  --engine <prior accepted P689 fteqw64.exe> \
  --engine-sha256 e9e992469ebb622bff68ac55774f83d81f3ca86a8513c102361fef04466f1c49 \
  --archive <exact ftesurf-0.1.25.7z> --receipt <matching receipt .json> \
  --feed <verified production-feed.json> \
  --runtime-root <fresh owned synthetic root> --evidence <fresh evidence root>
python -B tools/test_update_default_https_unit.py --work-root <fresh owned unit evidence>
python -B tools/test_updatefeed.py --work-root <fresh owned feed-test root>
```

The first command's exact invocation is retained in
`P689-HTTPS-ACCEPTANCE-RECORD.md` beside the results. Offline grader falsifiers:
**13 PASS** (`unit-04.log`): extra launcher/return arguments, wrong order,
unrelated actor, screen0/title return, product nonzero, wrong conhost exit and
complete exit census even when descendant or initiator grading fails; ordinary/extended-path correct
vectors and screen7 controls pass. Existing signed-feed suite: **12 PASS**
(`feed-unit-01.log`). AST, LSP and whitespace checks are separate from runtime
acceptance; no product compilation was needed or claimed.

Fresh review initially blocked three real evidence defects: substring argv
validation, accepting returning screen0 and incomplete failed exit census.
All were fixed and adversarially falsified before the complete run. Review and
parent disposition remain under `review-https-01.md`, `review-https-02.md` and
`REVIEW-DISPOSITION.md`. Final fresh review accepted the bounded06 result with
one report-only initial-nonzero census note. Parent fixed that note, added its
negative grader, then reran the complete final-byte08 matrix. Earlier rig
failures: receipt coverage assumption, marker prefix collision, overly broad
OS-helper exit assertion, unnormalized Rust executable prefix, premature initial
menu scheduling and physical input overwriting the synthetic hover between frames. No actual product
regression was demonstrated by these attempts.

## Limits and retention

This verifies normal Windows native signed checks/one-file content application
and engine repair/menu bootstrap restart against the unchanged **0.1.25/P687**
public release. It is not a new release upgrade, a P689 public feed, Linux native
HTTPS/UI proof, interruption/rename/crash testing or human acceptance. Opt-out
proves acted permission/status and unchanged ledger, **not zero public HTTP
requests**; prior counted loopback controls retain that independent evidence.
The harness only reads public endpoints; no feed/signing/publication occurs.

All eight large disposable synthetic release payloads were inventoried, their
unique non-secret cfg/state/log/PNG/sentinel evidence preserved, then retired.
Task process census was zero before retirement. Tiny `runtime-03` through
`runtime-06` and `runtime-08` folders retain only ownership notes and generated ephemeral
`identity.pfx` in place; credential bytes were not exported into reports and
are not public commit content. No prior task roots or real installs were cleaned.
