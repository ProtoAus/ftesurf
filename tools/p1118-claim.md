# P1118: prepare the selected saved state before placement

Claimed one max+1 patch after fetching both repositories and inspecting headings
and untracked claims. Runtime implementation is QC-only; native commit/tag pins,
state/capture formats, tier policy, KEEP speed, Build number and release unchanged.

## Change

Normal loading used a light identity read, placed the selected body, then reopened
the file for full application. A later rejection could retain the previous clean
admission at the new body. It now captures byte/row-confirmed rows and checks
selected identity plus the existing view-clock predicate before mode, recorder,
body or run-state changes. The prepared commit consumes those same rows.

The public three-argument apply API remains for retry/resume callers, preparing
and validating before application. Preserve valid loads, existing recorder-failure
containment, inherited classifications, zone-latch tail, legacy empty-line stop
and unread-tail suppression of an optional forgiveness grant. No new taint/reset
policy or data rewrite. This binds the state snapshot, not an atomic/authenticated
state-and-recording bundle or a general native writer/compiler audit.

## Verified

- An acting baseline reproduction and five production normal-load controls:
  rejected state leaves the previous body/admission untouched; valid moving/rest
  loads retain saved speed and existing classification. Retaining a clean old
  admission is correct when the old body did not move.
- Fourteen existing wrapper/grant/malformed/duplicate/empty-tail/upright cases,
  adapted to observe the current positive deferred request and call the actual
  FinishFrame helper. Synthetic empty-I/O phase, not native newmis-drain proof.
- One prepared-API unit reads valid rows, changes the real owned disk state,
  independently rejects its new rows, then commits the original valid buffer
  with saved speed and segmented classification. Not a measured automatic
  normal-entrypoint race/open count or a real ranked-finish acceptance.
- Two independent implementation reviews: OK with bounded evidence notes.
- Fixed full build: server/menu zero warnings; two unchanged upstream client
  F333 property227 warnings, zero NEW warnings. Initial source/fixture compiler
  and prediction failures remain retained, not relabelled as passes.
- Reader suite949 checks/zero failures. The same504 recordings and167 paired
  sidecars show no increased faults. Ten current orphan sidecars pass standalone
  structural checks; no missing recording or historical orphan cohort invented.

Private fixture code, raw observations and operational checkpoints stay private.
Human moving/rest load and retry/hold feel is pending in lextest.md. General
viewing/parked replay and the deferred general native writer/compiler audit are
not claimed complete.

## Delivery

Inspected runtime QC f6bfdb9bc98f2512ace00b9d3ac97cc1b8002c07 and engine
product-log e54355342eb4234a243ca1bec9d51adc0a0ae2bd pushed by exact SHA.
The clean runtime commit's normal build/deploy completed29Oct2026; dual Windows
three-VM/LNO copies and each immediate predecessor were hash-verified. Pi QW/CS
pair and .prev match; all12 once-restarted actors are fresh with unchanged native
images, positive empty status7 readback and healthy directory12 at11:28:10Z.
No PiForce. All16198/142 Windows and34737 Pi existing protected data/config/native
files retain their captured bytes; backend launchers/unit unchanged.

At11:31:51Z an isolated fresh client downloaded the actual served CSQC hash,
drew a9-column/type14 board and exited0 without QC error. Screenshot inspected:
board/map/tabs visible, but no zone/time rows; terms remain unaccepted. This is
served-code/drawn-frame acceptance, not ranked-finish, zone-content, load-feel,
HID/consent or world-visual acceptance. No owner client was signalled.

| VM | SHA256 |
|---|---|
| qwprogs.dat | c537e5e5ec2b0d82737613e8a1e63b48d268363cbef6272440512388d7f38078 |
| csprogs.dat | 3cca1ed606389ebc6703dde5c5d79fe3aa0ea8181299c1ea82cbde0a35d98a81 |
| menu.dat | f764f803e6ddbf97ba0fdec14774a32bfd5b86200afadc0ffa508ee9b4e78b39 |

Rollback: immediate canonical .prev for each copied artifact; immutable copies
of predecessors/prior-prev, exact source/artifacts/proof remain privately retained.
This documentation does not rebuild or redate the qualified runtime. No native,
backend, schema, threshold, Build or release deployment is part of this patch.

## Rebuilt with the 0-warning compiler (ftesurf-aa, 29 Oct 2026 12:33Z)

The 11:25Z install and lobby delivery was compiled by fteqcc git-6681-5662b3a23 (sha256
7ccb93d1, the main checkout's src/fteqcc64.exe). The two F333 property227 warnings above are that
compiler miscompiling cl_viewmodel.qc's setproperty(227), not upstream noise; the 0-warning
compiler is c24ede65 (C:\FTESurf-private\worktrees\knife-resume-01a16c7f\engine\engine\release\fteqcc64.exe).
The same main (e58f0a14) built with c24ede65 gives qwprogs df27e329 (this patch's server change
included) and csprogs 5fecc570 (no client QC change; already in tasrevd's codes.txt, which
3cca1ed6 was not, so its statements were skipped for credit). Now live on all 12 lobbies
(nobody on, restarted, lobby smoke 0 failures, 0 QC errors) and in both installs (qw + cs;
.prev = c537e5e5 / 3cca1ed6).
