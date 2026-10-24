# P963 — main-menu lobby chat and private messages

Predictions/falsifiers registered before implementation:

- Existing MENU-only, disconnected-only Friends proof still lists/joins and
  publishes presence. Add fixed `chat` read and `message` send operations, not an
  arbitrary signing API, lobby capability, account consent or credential export.
- A send binds target AND SHA256 of the exact UTF-8 text in the signed challenge.
  A changed body/target/domain, invalid signature, stale/foreign-peer ticket,
  unlinked/banned account, replay or active/connecting/demo client must refuse.
- Persist consumed message challenges in one short-lived additive SQL table;
  two worker connections must not deliver the same proof twice. No run, verdict,
  evidence, saved-game or existing relation rewrite; schema21->22 is additive.
- Public lobby messages are for proven linked accounts, respect blocks, expire
  after120s and are bounded. DM requires a mutual friend live in a lobby OR
  at the main menu; sender/recipient only, no unaccepted/blocked/third-party leak.
  Existing message text, inbox/global bounds and per-account action limits stay.
- MENU UI is one explicit chat screen with public room and friend conversations,
  polling only while visible and online-consented. Async requests are bounded;
  no automatic send/retry, plaintext disk cache, console text dump or localcmd
  containing text. Wire data renders as literal text, never code/format markup.
- Validate through existing Flask social fixtures (positive delivery plus
  refusals), actual fteqcc/native build, and a small owner visual/two-person check
  once matching client/backend are deployed. Source/static checks are not live
  chat acceptance. This feature is separate from the blocked old Native P954
  cohort; never relax or reuse its frozen source/actor/data gates.

## Implemented and isolated verification

- Existing `src/build.ps1 -Engine -NoDeploy -Jobs 8 -FteRoot <owned engine>`
  passes. All3VMs compile with zero warnings; native/plugin outputs retained
  without touching either Windows install or the Pi.
-60 real Flask Social tests pass (8.913s in this run). Healthy room/DM delivery
  acts; recipient/body/proof substitution, durable replay across connections and
  two installations, non-mutual/offline/blocked/banned cases refuse. Public/DM
  privacy, expiry, text/room bounds and21->22 additive/idempotent migration act.
- Existing account, board, join and replay scripts pass. Schema literal is
  consciously22; the existing account race fixture now actually races all24
  CREATE boundaries (old19 +3presence +2send-proof), not a stale19-statement list.
- Two actual owned native actors reuse the existing linked p615 rig: old client
  refuses chat/send; new client signs public/DM targets, and exact signatures
  verify. List/join/presence still act; malformed target/other domain refuse.
  The same production MENU helpers execute UTF-8 hashing, room/DM filtering,
  literal markup, retired/privacy-off callbacks and erased drafts/cache. No
  visual/two-person/live service acceptance is inferred. Only owned handles
  stopped; both canonical identity files stayed unchanged.
- Initial QC compile correctly rejected guessed UI/JSON interfaces and initialized
  const globals; fixed against existing declarations, then the SAME build entry
  passes. Account regression initially caught its stale statement-count oracle;
  updated explicit CREATE coverage and the SAME test passes. Neither initial
  failure is recorded as a pass.

## Clean integrated source qualification

Published P962 workshop prerequisites landed during validation and were merged,
not overwritten. The merged HL2 header required the existing Full/NoDeploy build:
Jobs1 (last working bounded-memory route),557.594s, clean QC source
c3bc153e2d423325d0fe43de464fd554659b2be2 and native
ce175aaa42d4f2763d8b414e2d09a7a022cbdebd. All3VMs have0warnings;
7freshAMD64PEs and5embedded resource ZIPs validate. Native warnings match the
existing74-line baseline exactly:0new. The final native SUBJECT executes again
and verifies the same proofs/production MENU helpers; old refusal evidence is
reused, not falsely claimed as rerun. No full extra regression campaign.

Native source tag patch-963 pins ce175aaa4. The ACTUAL compiled Makefile stamp is
`git-7789-patch-962-4-gce175aaa4`; a source tag is not substituted for that stamp.
Both feature sources are published. Later merges into native9ccaa87f5/QCa1f82713
contain peer documentation only, not new code or relabelled/redated build proof.
No release or Build number is implied. The initial artifact check used the wrong
DLL suffix; corrected to the documented x64/embedded-ZIP contract without
rebuilding or changing the passing product.

Status: matching schema22 Social service and BOTH Windows MENU/LNO copies
DELIVERED24Oct2026. Live service readback verified15:03:35Z; both menu destinations
verified15:21:41Z. The accepted80-file service closure changes only social.py and
surfd.py, preserves all historical values/bindings and native/reader dependencies,
and leaves all game processes unchanged. HTTP200, all12directory entries, actual
worker/importer/canonical bindings and OPEN serving admission were verified.
Both menu predecessors/prior-prev remain;13,011protected existing files compare
unchanged. No native binary or owner game was replaced/stopped by this delivery.

Earlier candidate/bootstrap refusals are retained as failures, not passes. The
bounded approved bootstrap completed through the existing importer transition;
no history restore or admission/freshness weakening. The old NativeClock handoff
was not reused. These are deployment/source/history checks, NOT live two-person
chat or owner visual acceptance. Lobby-side P961 producer delivery is now also
verified24Oct2026: all12lobbies have the current eight-field cohort; both Windows
retain their newer compatible published programs/native and the C3 menus. Actual
fresh-cache network CSQC/load/board-render check passes for the current cohort,
not a chat send/receive or live ranked-data query. Initial native/preimage refusal
and stale expected-hash smoke remain explicit in tools/p961-menu-presence.md.
Human-only checks: lextest.md. Run menu_restart before checking the new menu.
No Build/release bump.
