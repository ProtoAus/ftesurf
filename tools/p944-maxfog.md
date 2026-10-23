# P944 - personal Max Fog event

## Implemented and deployed; owner feel/credit decision pending

Event27's Zoomathon entry now carries explicit `mode maxfog` metadata. Story Play
passes a one-shot target-map/expiry/intent ticket to CSQC. Only the matching active
connection may request the mode; ordinary map launches, accepted direct joins and
cancellation clear earlier intent. A successful menu close must NOT cancel it.
The ticket is consumed on the server's mode ACK, not a permanent map-name rule.

`cmd maxfog 1` enables dense personal fog, `cmd maxfog 0` restores authored map
fog, and `cmd maxfog status` reports mode and whole-run eligibility (-1 unknown).
Native gamecode fog locks refuse ordinary console fog changes while active.
CSQC does not queue map/settings overrides behind the lock and refreshes ordinary
fog on the off edge. Commands target one player; no global fog controller changes.

A fresh timer start latches the mode. Switching it off clears that run's flag;
enabling it late cannot recover it. Only full fresh lobby finishes snapshot
`smaxfog` alongside the existing Story facts. Missing, malformed, partial,
untrusted, resumed or stage-only inputs do not become positive evidence. This is
trusted server-reported gameplay state, NOT cryptographic pixel/device attestation.
No movement, native pin/tag, body/journal, reader or collector change is made.

The backend supports a `maxfog` challenge and an additive Story column whose old
rows default to unknown (-1). Concurrent cron/gunicorn initializers serialize the
column check and ALTER in a short immediate transaction. A real two-connection
SQLite control reproduces the old duplicate-column race; the subject admits both
initializers and preserves the old row. **The default Event27 gold remains `finish`.** A
prechange public aggregate showed one gold holder. The owner was asked whether to
preserve legacy gold or require a new whole-fog finish; no answer/credit migration
is invented. Enabling the gameplay mode and recording future facts is independent
of that still-blocked criterion decision.

## Predictions and acted controls

- Ordinary fog renders normally; enabled mode visibly obscures distant geometry;
  `fog 0` is refused. Off restores actual map-authored air, sky and water settings.
- A fresh whole-fog walk/finish posts1; off-midrun and late-on post0. No repeated
  per-frame re-enable after manual off.
- Wrong-map and expired tickets produce explicit QC rejection, connected mode0
  and no enable message. A matching ticket survives a successful menu close.
- Unknown legacy rows never pass a maxfog challenge; trusted complete new rows
  agree in immediate answer, undated aggregate and dated ladder. Duplicate
  completed submissions cannot replace their original latched facts.

## Verification so far

All actual compiler directories are taken from `build.ps1 -NoDeploy -Jobs 8`
output, not guessed from `ftesurf/`. Three VMs compile with zero warnings.
Existing `surfd/test_story.py`:51 tests pass, including six new schema, fact,
metadata, answer/ladder and dated/full controls. Existing native runner's pure cfg
transport regression:four tests pass, with no native processes or player data.

Native installed compatible client/server, real dedicated loopback socket, fresh
private OFFLINE fixtures and existing `runlines_smoke.py` / P856 walkable-zone sink:

- Dense grey on-screen versus clear off/restored screenshots visually inspected.
  World/water256 and sky1 are positive native distances. Actual authored water
  restored to500/start100 on Parc Colore; air/sky restored0. Console fog0 refused.
- Three actual walked full finishes POST `smaxfog=1,0,0`, with nonzero timer/body
  controls and speed facts. This local scripted sink does not establish live
  online/ranked acceptance or physical-input authenticity.
- Separate wrong-map and expired native arms explicitly reject their request,
  return mode0 and never enable fog. They are not silence-only controls.
- Earlier intermediate failures remain recorded: wrong artifact-copy seam never
  ran; bare `ui_close` needed `menu_cmd`; negative fog changed getters but not
  pixels; a broad map-line rewrite mangled a `_map` cvar; WorldLoaded saw an empty
  server map before the connection became active. The reusable seams were fixed,
  not bypassed with new launch wrappers or weaker freshness checks.

The unpublished source checkpoint was based on5992a5ef and rebased onto inspected
b5965bf0, preserving published P941 presentation and P942 verifier changes. P943
was already claimed elsewhere;944 is the one claimed number. Engine ledger commit
fdb69ce974eb1d6009c211f49e42759616b0952c is documentation only.

## Delivery receipt — 23 October 2026 UTC

- Published feature source858ec1a5; laterd353c990 is a test-only SQLite proxy fix.
  Qualified backend variant39088d3d is published on
  `deploy/requests-20261022-p944-schema20`; it preserves the serving schema20/hid-v1
  family and exact published P942 sweep. Onlysurfd.py changes in the80-file runtime.
- Both Windows DAT/LNO sets matched the qualified artifacts at08:04:31Z, with
  `.prev` and older generations retained and native/config/metadata unchanged.
  Later Windows successors were preserved, not overwritten or claimed as this
  receipt's current byte identity.
- After an actual player caused the ordinary Pi invocation to refuse, the owner
  explicitly authorized the forced update. The same build entrypoint deployed
  QWe7cf5f3a / CSQC615f1316 and restarted all12lobbies. System-unit readback confirmed
  all12active/running, matching destination hashes and retained predecessors.
- Backend-only cutover used the already qualified CLOSED candidate, independent
  product/adapter reviews and a checked whole-step SQLite backup. Exact master/
  importer epochs, source/cron bindings, actual workerorigin/hash, schema/profile,
  admission and importer-lock readiness were checked. No game or AI signal was
  issued by this cutover; all12game epochs/native/progs/config bytes stayed fixed.
- At10:09:04Z the live API served catalogue revision`ef89114c8a23`: Event27's
  `surf_zoomathon` mode is`maxfog`. The actual owner-maintained catalogue changed
  by ONE mode line; its original bytes and backup remain preserved. Gold stays
  `finish`, the public gold-holder count stays1, and all62legacy Story rows remain
  unchanged with maxfog unknown. No historical credit or positive fact was made up.
- Corrected ARM Story50tests pass (the older qualified stock catalogue lacks one
  preexisting main-only test). The staged suite's only failure was three acted
  missing-context-method errors in its SQLite test proxy. The exact published
  corrected fixture passes; the original failed suite/archive/runtime are retained
  and its resolution is explicit, not a rewritten successful log. Nine bounded
  handoff controls and actual wrong/correct catalogue-CAS controls also acted.

The reusable Story publisher now accepts`--expected-live-sha256`, uses an owned
upload stage and compares the inspected predecessor at the rename boundary. The
one-line catalogue was validated and promoted through that existing entrypoint;
no parse/medal rule or force bypass was used.

No release or Build-number bump was requested. Owner visual/feel, actual menu
click and second-client observation remain pending in`lextest.md`; the existing
gold-credit policy is still a concrete owner decision. This receipt does not turn
local scripted facts into hostile-renderer, physical-input or ranked acceptance.
