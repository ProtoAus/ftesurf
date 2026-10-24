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

Status: verified in isolation; source commit/push and matching deployment pending.
Do NOT mix with the older NativeClock delivery cohort or reset its gates. The
serving service must match schema22 and this Social implementation before the
heartbeat/chat menu ships. Human-only checks: lextest.md. No Build/release bump.
