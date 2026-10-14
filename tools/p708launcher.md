# P708 — black, slim, continuously styled World of Surf launcher

## Product scope

Launcher-only product source in ProtoAus/Quakers-Launcher, based on inspected
P704 main4a002784eee05c208ba5f6336270d15e42318be9. P705 web/brand, P706 KSF and
P707 parallel website routes were independently published before this feature;
it takes max+1 **P708** and does not ship or alter those peers' product work. Engine product pin/tag, QC Build, signing
key/feed, player settings/data and native/QC binaries are unchanged.

- Black background throughout; existing cyan/purple text-only logo stays centered.
  The full32-cell logo remains at80x24,60x24,40x20; compact only below34 columns
  or18 rows. Narrow footers shorten instead of being giant clipped controls.
- Small borderless Yes/No choices. Up selects Yes, Down selects No, Enter accepts
  the selected answer. Y/N/Esc/Q/Ctrl-C shortcuts and automation remain supported.
- Empty install: **Download World of Surf?** with service/IP disclosure before
  network. Its first Yes approves consent and the first download, with no second
  large prompt. No exits0 without any feed/object request, consent write or game
  files. Existing installed opt-outs remain unchanged; an empty install previously
  declined can be asked again rather than getting a misleading missing-game error.
- One owned alternate screen/raw-input session covers checking, download,
  installation, play and interactive errors. Async operations update the same
  styled page; no transient println/main-screen detours. Error close uses Enter
  or Esc in the same black layout; logs retain the full failure after exit.
- Slim downloader: exact total network bytes **this session**, receive speed,
  verified-file meter/count and package size, four current filenames/thin per-file
  meters. No category/release/mirror/dashboard boxes. Source passes concurrency4,
  not three real workers with a cosmetic fourth row.
- Repeated network bytes do not imply verification; resumed per-file offsets are
  distinct from new network bytes. A full staged-file meter reads checking until
  successful hashing. Overall299/300 remains99%, not100%.
- Download questions show only the size, not canonical target paths. Windows
  `\\?\` is internal long-path notation, not part of the folder's human name;
  filesystem safety checks/canonical paths themselves remain untouched.
- P704 source-checkout protection and detached Windows game spawn remain intact.
  Only the launcher is deployed; no public release/feed or fleet operation.

## Verification

- Optimized locked offline Windows build: **zero new warnings**, size
  **3,596,288 bytes**, SHA256
  `d2efa5c473d793bf05157df0c58f95fc498e7ac5080dc18ffad5eb91284884f0`.
- Rust library: **42 passed**, zero failures. Actual cell matrices at100x32,
  80x30/24,60x24,40x20,34x18 and tiny/zero sizes check centered full/compact logo,
  black backgrounds/shared phase geometry, small choices, key selection,
  retransmit/resume-versus-verification and animation versus fixed progress.
  Final cell-backed PNGs inspected, not just claimed from source.
- `tools/test_launcher_ui_windows.py` uses a uniquely owned native ConPTY and
  actual **ResizePseudoConsole** (the Windows Terminal protocol), not an API that
  pretends a requested resize happened. Live initial/check/download/play/error
  frames at80x30,60x24,40x20 preserve black cells/full logo; Up/Down/Enter acts.
  Input mode remains raw across phases and restores at exit. Actual VT streams
  contain **exactly one alternate-screen enter/leave pair** per entire workflow.
- Fresh No makes **zero requests/files**. Fresh Yes requests one signed feed and
  reaches verified installation without a second download prompt. Four distinct
  object requests are frozen before any response body, proving **four real
  simultaneous workers**; the P704 control demonstrably has only three. Counts
  refer to these held requests, not provider callbacks lingering after delivering
  their final bytes. Final installed synthetic files match all signed bytes.
- Esc cancels after actual bytes; providers drain, partials remain and no live
  file/journal promotion occurs. An unsigned feed reaches the styled error page,
  makes zero object requests, and Enter exits1 with raw mode restored.
- Complete existing `tools/test_update_launcher.py` signed-update, recovery,
  held-lock, link/junction, corrupt/old feed, in-game and offline regression passes
  against final bytes. `tools/test_launcher_dev_handoff.py` passes dev .git
  file/directory refusal/zero-network plus direct AND actual batch Enter spawn:
  persistent actor alive, console gone, exact args/CWD. Retained P694 preview
  acts as the waiting negative control; P704 was already detached.
- `tools/test_reccheck.py`: **306 checks,0 failed**. No evidence/reader semantics
  or live recording corpus was changed. LSP has no recorded diagnostics; that is
  not substituted for compilation/native acceptance.

Failure history remains separate under the owned root: classic window/buffer
resize was ignored by the default terminal host; initial ConPTY child inherited
redirected harness handles and was not a TTY; a new-console trial did not meet the
hidden-fixture contract; the first concurrency counter included post-delivery
provider cleanup; a handoff trial supplied already-detached P704 to a wait oracle.
Final fresh matrices use explicit ConPTY handles/resize, held-request counts and
the correct baseline. No failed run is relabelled PASS and no owner game/terminal
was stopped. An explicit missing-executable ConPTY control also verifies launch
failure cleanup and restored parent handles/no orphan drain thread.

## Delivery / limits

Windows launcher disk delivery **PASS**, 2026-10-14T16:19:59Z:

- `C:/FTESurf/ftesurf-launcher.exe`
- `C:/Users/Lex/Desktop/New folder/ftesurf-launcher.exe` (the explicitly referenced
  test copy, not an inferred install)

Both match the3,596,288-byte SHA256 above. Published launcher product commit is
`7ad9499dcecb0618bb7412f7a33f5464bd81d17a`; the immutable disk receipt records
then-inspected prepublication `88787aba3b01c391d83f51bb5d1d333a7115718c`.
Their product source/dependency trees are identical to the tested code; only
unpublished subjects/numbering changed after peer P706/P707 publication. Existing normal install
locks were held, target game/launcher processes were absent, and unique
`.pre707-20261014T140310Z` copies preserve the exact old P704 executables. All
allowlisted game artifacts remain byte-identical; no owner cfg/data, updater
consent/ledger or native/QC deployment. Primary `--yes --no-launch` acts on the
development guard; the Desktop executable was not run against owner metadata.
No game/GPU work was launched after the operator's explicit GPU-test coordination
instruction; existing other-session processes were neither stopped nor changed.

Guarded clean-commit launcher delivery is recorded separately in the same owned
root `C:/FTESurf-worktrees/launchfix-20261014T140310Z/`, under ui705-* filenames
(the pre-claim run label, **not** the independent P705 web patch). Preserve old
launcher bytes under unique same-directory predecessors and immutable artifact
copies. Primary and explicitly referenced Desktop/New folder copies are eligible
only if still the exact known P704 executable and not currently running. Do not
replace game binaries/config/data or the differently named second-install engine.

Limits: native owned ConPTY, not a physically inspected Windows Terminal window
or a newly launched real game. No Linux runtime, public archive/feed, native/QC
build or Pi delivery is claimed. Human appearance acceptance remains the owner's.
