# P1058: crisp native-size text, floating header, persistent development MENU

## Cause and change

Owner reported scaled text, requested a detached top bar and said the new MENU
vanished after restarting. Home used11/18/22, outside the UI baked ladder
8/12/16/20/24/28/32. Use12/20/24, integer layout origins and separate compact
stat labels/values. Do not change owner font/filter/video settings.

The rounded header and body form one centered group, max1660x988: header56,
gap12, body remainder. Home uses that already-inset frame, without double
subtracting a gutter. This keeps large lobby images, compact stats and tall
Friends; all12 lobbies and all stat/mode rows remain visible.

Primary's replacement MENU is557482 bytes and EXACTLY matches the signed public
0.1.31 BLAKE2b-256 record. Native ingame manifest/state timestamps line up with
the04:42 replacement. Earlier peer/stale-build attribution was unsupported and
is withdrawn; that does not establish every older overwrite's actor. The native
FTESurf updater deliberately checks per-file differences even at the same version;
MU_Poll automatically applied the available release over the development menu.

Default/manual source builds now compile UI_MENU_DEVELOPMENT1; explicit
build.ps1 -ReleaseVersion compiles0 (release.ps1 already supplies that argument).
Development keeps signed checks, permission and native safety, but requires an
explicit F2 "Install release (replace dev)" choice before applying. Published
release-mode menus keep automatic installation. This is not a native verifier,
transport, ledger, consent, security-key, release-version or qcbuild change.
Native/server/API/website binaries and prior on-demand CS:GO preference stay put.

## Verification

Owned root: `C:\FTESurf-worktrees\menu-20261026T1632Z`; predictions:
PLAN-home-crisp-persistence.md. Existing runtime runner:
`python <root>/home-fit-smoke.py subject crisp`.

- Dev and explicit0.1.31 release-mode NoDeploy builds: server/menu0 warnings;
  same two untouched CSQC setproperty227 warnings, zero new.
- `artifacts/home-crisp/subject-7bbf35ad41`: real populated local fixture at EXACT
  1280x720,1920x1111,800x600.12/12 targets,9 populated WOS/Everything rows,
  Story2/4 and Event1/3, source switches, bottom bounds and64-cell/legacy/offline
  cases pass. Floating header x/y>=12, height56 and12px gap to body; matching width.
  Screenshots inspected at all sizes; compact labels and title are visibly crisp.
  This is synthetic layout evidence, not linked-account or owner feel acceptance.

### Real signed native updater control

`menu-persistence-smoke.py` uses the existing Runtime/overlay, updatefeed and REAL
launcher --dir OWNED --no-launch entrypoints, loopback only. The native fixture
correctly refused without launcher state; actual launcher adoption fixed that
setup, without fabricating a ledger or loosening a native check. No public feed
was published; secrets stayed inside the signing helper and were never printed.
Signed fixtures/raw local evidence MUST NOT be exported from the task root.

`artifacts/menu-persistence/launcher-adopted/result.json`:

1. Native release-mode control automatically fetched and installed the signed
   old-release MENU: subject ACTED, not a silent no-op.
2. Development reached available with the same signed delta but fetched0 object
   files, kept its MENU bytes and kept consent/ledgers across TWO fresh processes.
3. Explicit F2 GUI switch then ACTED and installed the signed expected old MENU.
   The button/warning screenshot was inspected. Native permission stayed enabled.

The first helper/build-call assumptions and absent-launcher-state refusal are
retained as tooling failures, not passed product arms. An invalid @-argument
ui_click went to0,0; it rewrote ONLY the local fixture's enabled consent LF->CRLF
and did not install. This is a failed MANUAL arm, not an automatic-boot change.
The already-passed release/two-boot assertions were reused (not redated/repeated);
corrected manual action used ui_hover then ui_mouse down/up and was bound to
current exact metadata hashes. Canonical binaries/MENU remained unchanged during
all controls. No all-platform/full-native-security-regression claim is made.

An inspected clean engine worktree was essential: the dirty canonical branch
had older updater code without the current MENU interface. Read b1e3b1aff/current
published source for this contract, not that stale sibling branch.

## Delivery / retention

INSTALLED BOTH Windows menus at2026-10-27T06:01:02.142067Z. Source feature4ae67a48,
inspected clean published integrations7fef551c87157f12b9497a976d216e88be10fb27;
engine-doceba5802aa. Final clean integrated build is BYTE-IDENTICAL to the tested
UI/native-development candidate. SHA256:
`6d52df34c02a9ec205ce8c294d318a374fc8e8a4b00af61003d8f511afde53f9`
(582498 bytes), verified at BOTH destinations and in immutable staging.

`artifacts/deploy-p1058-home-crisp.json` binds actual UTC, source, previous/new
hashes and adjacent menu.dat.p1058-20261027T060102Z.prev rollbacks. All36 captured
present/absent protected entries stayed unchanged: CURRENT native binaries,
plugins, gameplay progs, updater consent/state/installed/cache/journal,
installed.lst, saved configs and the approved CS:GO setting. Native changes that
arrived separately during the wider session were preserved, not reverted.

The first pre-swap guard rejected a mis-transcribed secondary hash before ANY
write; expected values now come directly from immutable prior receipts. A foreign
process gate then correctly blocked; those PIDs exited naturally before the
fresh successful boundary. No process stopped and own short claim released in
finally. No new API/site/server/native deployment is implied. Source/staging and
needed evidence are retained under the owned root; verified disposable generated
outputs/links and the clean engine-doc worktree are retired separately. Owner
font/header feel and normal-launch confirmation remain pending in lextest.md.
