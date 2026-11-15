# P1568 — bounded large completed-run history delivery

15 Nov 2026 UTC. Development deployment, **not a release**.

## Player-visible scope

P1564 keeps completed ordinary, slower/non-PB, segmented and TAS recordings as
separate local-history entries, with authenticated background acquisition and no
automatic playback. TAS has its own assisted community board and does not earn
ordinary ranked points or native certification. Existing recordings are not
retroactively assigned to an account.

P1568 removes the updated owner-history transport's old 8 MiB acquisition cliff.
The finite safety ceiling is **1,073,741,823 bytes**, not unlimited storage.
Unsupported/older ends retain their legacy limit and server originals. REC grammar,
movement, trust, consent and rank policy are unchanged. See
[p1568-large-history.md](p1568-large-history.md) for the transport contract.

## Source and qualification

- Native: clean published `cc56219a3c7e2a99128cc8ff02285d57a25e422b`, annotated
  `patch-1568`, stamp `git-8769-patch-1568-0-gcc56219a3`.
- QC: clean published `5abe4f89ca88c8b2b5c62581f1ed3b16fe4420c3`; the later
  published `475858ab5c9d96e2c6f1278dda926a89c3a8b0b7` has byte-identical
  `src/`, `ENGINE.txt` and `VERSION`. The qualified artifacts were reused, not
  rebuilt to change provenance. Published peer changes were integrated; no
  uncommitted peer source was deployed. The later delivery-only tooling commit
  `2e191c4dfcdc8a4f8bbeed8f55514fe02c3cacb9` changes the directory URL seam,
  not QC/header/ENGINE/VERSION inputs or these qualified DAT bytes.
- Full Windows client/server/five-plugin build: all 74 baseline warning
  occurrences matched, zero new warnings. Canonical Git-blob ARM64 build:
  all 16 baseline warnings matched, zero new diagnostics. Actual Windows and
  ARM64 dedicated images each passed 1,831 map-free selfchecks, zero failures.
- Final clean three-VM QC build: compiler exit 0, three zero-warning reports.
  Independent native, QC and final merged-integration reviews are clear.
- Final candidate reader output reports 957 checks and zero failures; its original
  child exit status was not persisted. Paired CLI corpus checks retain the same 762 input
  byte hashes: 578 REC, 174 paired VIEW and 10 unpaired VIEW; both readers report
  366 faulty cases and 368 diagnostics, zero new fault cases. Historical failures
  were not silently regraded.
- A genuine final-build TAS completion used a real dedicated socket, account
  proof and authenticated list2/get2 transfer; the complete local copy matched
  all 32,353 bytes and passed strict reading. No automatic replay occurred.
  That arm retained a separate run-announcement leaf-metadata warning; the full
  server original and authenticated local acquisition still succeeded. Community
  replay-link metadata for TAS/long leaf names was not qualified; see BACKLOG.md.
- A clearly synthetic **17 MiB + 3 byte** opaque body exercised pending recovery,
  production owner sealing, full transfer/ACK, persisted client hashing and
  byte-identical promotion. Its pending promise was modeled: this is transport
  evidence, not a genuine long REC completion, submission or certification.
- A read-denied/write-open-existing sentinel refused locally with its exact bytes
  and DACL preserved. A late final sentinel survived an actual transfer beyond
  8 MiB, but full-body promotion refusal was not measured.

Genuine >8 MiB completion/native pending creation, a healthy same-context listing
lasting over 30 seconds, arbitrary-size handling and memory/performance claims
remain unmeasured. The interrupted genuine long capture was not adopted or
resumed as a completed run.

## Development delivery

### Both Windows installs — accepted by read-only destination audit

The scoped promotion copied all 22 native/plugin/DAT/LNO targets (18 changed,
4 already identical). Its original producer **failed after copying** because its
receipt field was missing, leaving its own lock. That failure is retained; the
producer was not replayed or relabeled successful.

At **2026-11-15T04:36:20.268547Z**, a separate read-only audit accepted all 22 destination hashes and expected
current/previous images, with all 20,540 pre-existing protected paths unchanged
in membership, bytes and metadata. Only the verified completed task's own lock
was released. The future caller now validates receipt paths before mutation and
releases its own lease even if receipt writing fails; two acting isolated
controls cover that seam. No owner game was killed or source/data restored.

Qualified client SHA256:
`ed09b442151cab5e2e788a8c0cf0014c5c34602ec84b2c717595ccbb4e97ed09`.
The supported cache seeder created only absent `f8db93d4.dat` leaves in both
installs. That folded MD4 cache identity is **not** the full-SHA256 authentication
allowlist identity; no existing differing cache body was overwritten.

### Native Pi — normal-success accepted

Activation at **2026-11-15T04:38:51.134880Z** restarted all 12 lobbies once with
the ordinary 10-second warning, no force or fallback retry. Normal-success
postflight accepted at **2026-11-15T04:42:56.664832Z**. The actual resident backend
namespace also sees the qualified
ARM64 native image:
`0200f5194751fb6d0dcada8f47a874c81c5a810248536ee94ede466b390fbfbe`.

Fresh before-state archives retained the four current/previous native/plugin
images, all nine parts and all 198 resume/state members, with member hashes and
metadata checked on-box and off-box before staging. Normal-success postflight
accepted all 12 new process births/native/plugin identities, unchanged immutable
backend/source/dependencies and all 64,643 old protected paths. Existing progs,
menu, configs, part and resume bytes/metadata were preserved. New files were
reported separately, not hidden by an expiry/deletion exception. The serving
fleet was not restarted again to repair an observer.

### QC Pi — paired rollout deployed; separate read-only acceptance

Qualified server SHA256:
`9cd4a2cac26fcaedd598d0187303f71f272dba1edf35bf7fb5f13ab74e7aaf50`.
Qualified client SHA256: `ed09b442...` above.

The owner-approved current-cohort operation ran once from
**2026-11-15T10:32:34.828623Z**. Both strict M/F preservation boundaries passed at
**10:34:37Z** and **10:37:05Z**. It executed all 45 official statements once, no
rehydrated setup, one lease wrapper: uploaded/hashed only QW/CS, warned all twelve
ports, waited ten seconds, swapped the pair with old current images as `.prev`,
and restarted all twelve lobbies once. The caller completed by **10:37:17.682316Z**.
No native/config/backend/Root/menu deployment occurred in this transaction.

The driver then **failed its first normal F.post** on a UDP status timeout inside
`B.status`, before an F.after record, M.post or supported live readback. It exited
at **10:37:23.670849Z**; the owned kernel holder exited0 and both owned leases were
released. That failed receipt remains failed and immutable. No second upload,
swap/restart, rerun of the original normal postflight, rollback or baseline reset
followed.

#### Separate read-only current-state acceptance

One bounded diagnostic at **2026-11-15T10:46:24–10:48:32Z**, exit0, verified:

- All **12/12** active, new native PID/births versus cold predecessors, unchanged
  native `0200f519...` and valid plugin mappings. All twelve process-root QW/CS
  full hashes equal the qualified pair.
- Exactly one healthy, empty UDP status call and one supported hashed serverinfo
  command per port. All twelve returned CSQC **4175139796 / `0xf8db93d4`**, size
  **5,515,406**, history enabled, a valid epoch and current map fields. Public
  HTTPS directory had twelve fresh, empty rows.
- All **64,842 saved cold protected entries**, **20,084,682,968 bytes**, retained
  full hashes and full protected metadata. All **204 selected members** retained
  exact inventory, full hashes and metadata, including parts9/resume195.
- Current backend/source dependencies159, policy comparisons, known configuration
  and codes143 passed the selected strict comparisons. Current required-actor
  FD census passed for15 actors, stable native births and the existing backend
  before/after closure checks.
- Four canonical full hashes equal the expected candidate-current / predecessor-
  previous transition. Both `.new` stage names are absent. Diagnostic errors0.

This is **separate, nonleased, one-status-window evidence**. The original normal
F.post → M.post → supported-reader chain did not complete, remains failed and was
not recreated under its original output names. Existing strict definitions were
source-sealed and loaded before dispatch; normal write entrypoints were trapped
and never called. The full second F observation was not replayed. Existing two
protected-login NONactor descriptor permission limits remain explicit; this is
not a universal privileged-writer audit or an inventory of every later unselected
DATA addition. Original207 custody was reused, not recaptured or relabeled.
Parent component-level acceptance was recorded after independent evidence-scope
review: deployed and verified during this diagnostic window, **not** successful
original normal-method completion. No additional host action was required.

The initial missing UDP response's cause and failed port remain **UNKNOWN**.
Systemd starts spanned10:37:08–10:37:18Z, with automatic restart counters0 at the
later observation. Current health does not establish historical application-ready
time. A bounded journal query exposed0 records; lobby logging/ordinary-user
visibility did not support a historical startup/QCVM-error verdict. No clean-log,
startup-delay or performance claim follows. No further deployment is indicated by
the actual healthy current state and exact cold-domain preservation proof.

#### Historical refusal and specifically authorized fresh derivation

The ship set is the existing two-DAT route. Menu/LNO/native/plugin and
histories are protected, not extra promotion targets. Fresh cold custody accepted
all 207 part/resume members and four current/previous program members on-box and
off-box, with all archive hashes and member metadata checked. The protected
baseline held 64,711 filesystem members plus the external codefile; original
refusals and every older evidence byte were preserved.

The real pre-upload guard then found a cold-backed resume member absent from the
live tree. It refused **before any DAT upload, `.new` staging, swap, warning or
restart**. The owned kernel lease and local rig lease were released normally.
No expiry exception, restoration, deletion, rebaseline, Force or automatic retry
was performed. The old source-stage backups, current installed program pair,
normal `.prev` lineage and full verified cold archives are retained.

One read-only observation at **2026-11-15T08:49:05–08:49:25Z** confirmed three
missing members from one resume slot; the other 204 original members have
unchanged full hashes and metadata, including all nine recorder parts. All four
canonical current/previous DATs still match the old cold hashes; both `.new`
paths are absent. The three missing members' archived bytes still match their
original hashes. The 64,711-member metadata comparison found only those three
old paths missing and no other old metadata change, plus 100 new unrelated DATA
files. General surviving DATA/new-file contents were not freshly hashed; this
was not an atomic global snapshot.

Attribution remains **UNKNOWN**. Calendar age 15 days is compatible with the
configured/default 14-day resume-cleanup contract, but effective runtime policy
and the actual removal operation were not established. No candidate DAT was
uploaded, so this is not evidence that the proposed DATs deleted anything.
The owner explicitly approved accepting only those three known absences and
taking a fresh preservation baseline, keeping the original archive untouched and
not restoring the slot. That disposition does not prove expiry, waive other loss
or make the original failed transaction replayable. Fresh current materialization
and F/M cold capture ran **09:52:19–10:00:30Z**, exit0: 64,841 protected game members,
64,842 extended rows including codes, 204 selected members (9 parts/195 resumes),
159 current backend dependencies and 143 code entries. All current additions
were bound; the only other old protected replacement was the exact published,
already owner-installed peer configuration described below. Current actor/FD and
12 positive-empty checks acted. All 204 selected, four canonical and four history
payloads were individually hash/metadata verified off-box; identical receipt and
archive seals were verified on-box. The later one-time transaction and initial
postflight failure are recorded above. Restoring archived player state is a
separate decision and was not requested.

Earlier tooling refusals are distinct: a placeholder check matched a legitimate
schema key before local staging; the next call staged only the owned local pair
then refused at the retired LAN directory port. The official tool now separates
`PiDirectoryUrl` from SSH transport, defaults to public HTTPS, and retains all
unknown/missing-row, warning/countdown and explicit-only Force policy. Eleven
actual-source mock controls plus the actual HTTPS directory block passed. Exact
read-only-front continuation was independently reviewed; it did not recopy local
fixtures or overwrite failed receipts. None of these wrapper/source controls is
claimed as completed fleet delivery.

Code allowlist registration is complete: 142 to 143 unique entries, full qualified
CSQC SHA256 added exactly once, existing inode/owner/group/mode and every old
entry preserved. Exact raw preimage was saved off-box before writing and in the
ordinary on-box `.pre1568` backup; no Root or service restart.

## Online TAS — observed serving, not activated by this transaction

The serving peer generation already contains the TAS backend. At
**2026-11-15T05:07:59Z**, live public `/api/board` accepted the separate
TAS/community style and tier with HTTP 200;
segmented control also returned 200, while an invalid style returned 400. The
checked stage-2 `surf_tensor2` TAS scope currently has zero rows. This is not a
fresh production submission claim.

At **2026-11-15T05:22:59Z**, the website's actual
`https://proto.bar/ftesurf/board/board.js` returned HTTP 200 and included the
TAS (assisted) selector. At that observation its bytes differed from current QC
source that also included later helped-run UI work; the 05:23 observation was not
a claim of that later UI being live. A wrong game-vhost URL and an over-strict
current-source-equality observer failed and are retained; one bounded readback
saved the actual served bytes.

The old staged Root/backend proposal was **not activated** and is now obsolete
for this task. Do not run it or treat the earlier policy-approval discussion as a
remaining TAS blocker. This task did not run a Root installer, backend swap or
policy update.

Separately, the peer P1569 task records the owner's 08:42:58Z policy installation
and its guarded backend transition completing at 09:18:15Z on primary `6ec84932`
/ `backend-15665948`, with old `f443f6cf` closed. It published/deployed
`lobby_helped 1` (`b4379a06`, exact lobby-config SHA256
`fcb68641b931fc00a264312656734e608519e9569dc6ce3b19647742c0996128`) and read it
back effective on all twelve ports, without restart. Those are peer delivery
claims in [p1569-delivery.md](p1569-delivery.md), not actions repeated here.
The fresh QC cohort must observe/bind the actual current external context and
preserve that already-deployed config, rather than claiming old source/actors
remain current. The three new public commits change only config/docs; compiled
QC/ENGINE/VERSION inputs are unchanged. No first real production TAS posting or
native certification is claimed.

## Human checks and retained workspaces

Owner menu/replay visual acceptance remains pending in `lextest.md`, including
the original surf_sandtrap2 bonus-4 replay. Automated angle-source checks do not
substitute for looking at that replay. A normal finished TAS is needed to
exercise first real production posting; no fabricated leaderboard row was added.

Unique source, qualification, failed attempts, before-images and rollback custody
are retained. ARM object retirement refused before any deletion because complete
same-UID process/descriptor inspection was unavailable. Its owned 54.9 MB build
outputs remain in its intentionally retained-blocked/not-active tree; no permission
escalation, cleanup retry or root move was attempted. The 54.9 MB is the recorded
generated-output set, not the whole source/evidence tree. No release/build-number bump
or engine retag occurred.
