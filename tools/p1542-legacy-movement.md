# P1542 - experimental legacy movement candidate

Status: **local candidate, not pushed or deployed**. This continues the earlier
unpublished P1527 prototype on the inspected current engine/QC source. It is not
a completed full HL1/AG/HL2 implementation, a release, or a parity claim.

## Available implementation

The server and prediction share two explicit map-spawn selections:

| Selection | Advertised context | Scope |
| --- | --- | --- |
| `default` or empty | existing default | Existing Source movement |
| `ag-100` | `ag-100-v1` | Experimental unranked 100-rate practice |
| `ag-250` | `ag-250-v1` | Experimental unranked 250-rate practice |

A selection is applied when a map spawns, not a live mid-run mode change. Unknown
selectors and `ag-1000` are refused. A fixed simulation rate is not proof of the
original client's frame-coupled schedule. Authentic 1000 behavior still needs a
qualified reference; the requested HL2 eras have not been selected/implemented.
The v1 contexts do not provide longjump equipment, and ladder intent uses analog
signs. Do not label this full stock HL1 or exact AG compatibility.

The shared path includes bounded command timing, crouch transitions, stairs,
water/ladder handling and carried waterjump state. Optional state is explicitly
identified and practice remains unranked. Saves, replay state, resume slots and
recording parts use closed profile-specific namespaces; default paths remain the
existing paths. Unknown/cross-profile metadata is refused before mutation. New
QC comparisons use string contents rather than dynamic string identity.

Historical AG disk rewind export is still unsupported where the full carried
waterjump state is unavailable. That operation refuses without replacing the
existing save. This is an explicit limit, not an unknown-to-zero reconstruction.
Ordinary Source rewind and save behavior is not intentionally changed.

## Evidence already completed

- Current-main source integration retained the published landing-observation
  correction and the peer QC changes. Independent movement/evidence review
  cleared the actual code scope, including the new QC content comparisons.
- An isolated Windows Full invocation compiled client, dedicated server and all
  five required plugins. Server/client/menu QC each emitted zero warnings. The
  native warning multiset exactly matched the retained baseline: 74 total,
  zero new signatures or multiplicities. This is not zero total warnings.
- The current reader passed 949 checks with zero failures and seven focused
  profile-identity controls. Against the exact published baseline on identical
  stable bytes, 568 recordings and 173 associated views retained exactly the
  same fault sets. Existing faults are not a clean-corpus pass; unassociated
  views and other explicitly uncovered files are not inferred valid.
- The earlier ARM64 verification candidate passed all twelve current dettest
  arms, with 90 named candidate/baseline rows exactly equal across six maps.
  Both historical pin2 arms also passed. Those are earlier-image results,
  **not execution evidence for the newly merged binaries**.
- Both corrected-input historical pin7 arms subsequently passed 9194 ticks /
  9192 rows each, completing the earlier-image 16-arm execution matrix. The
  qualified missing zone input and all five fixtures have final preservation /
  actor-cleanup closure evidence. Original failed cases remain failed; the
  one-case/parser-only CLI does not claim global platform acceptance. This does
  not qualify current merged images, rendered play or optional AG reference parity.
- Actual headless dedicated-server/client cases passed the 100 and 250
  save/load and carried-waterjump controls, including active zero state. Cold
  CSQC startup needed a review-only 40-second world window for eight timed
  phases after restore; the external input deadline and actor limits are
  unchanged. Review phases and map-switch cycles now require separate cases.
- A real 100/default/250 map-switch check caught incomplete initial AG context:
  the original client correctly refused mode2/version0 on the final map.
  Prioritizing the three closed-context keys in the existing signon snapshot
  fixes this acting case without weakening the guard. The same strengthened
  helper then observed a live final client, positive directional input, body
  displacement and advancing ticks at .004. Server strings alone cannot pass.
  Fresh bad-version and missing-version cases still refused; a fresh default
  Source control passed. The unsupported 1000 selector correctly refused.
- The new priority-source incremental NoDeploy build completed all three QC VMs
  with zero warnings. An initial standalone probe compile failed before native
  actors; its diagnostic retry had an incorrect overlay path, not a repeated
  allocator failure. Both failures remain retained. The normal helper retained
  its exact manifest and subsequently compiled and ran the acting paired cases.

## Build and delivery limits still open

The clean local `1bfa3eae138c70ad94e05416dfd96fc0cb327cb4` Full cohort compiled
with `git-8735-patch-1542-0-g1bfa3eae1`: seven fresh native PEs, QC zero warnings,
all 74 native warnings exactly matching baseline, and all five actual plugin
ZIP payloads passing the real LF/braces/field/token/CRC contract. Earlier 92d
literal-backslash-n products remain preserved with their metadata HOLD. New
products were not normalized or repacked for acceptance; no runtime package
parser or public-redistribution clearance is inferred. The former unpublished
tag objects remain preserved; no public tag/history was replaced.

The signon priority fix follows that cohort at reviewed engine commit
`47998d6e3129978559d123e3334406cb95b0526b`, local tag `patch-1542`, and passed
the actual paired headless checks above. At this source checkpoint its clean
commit/tag-bound Full remains required before deployment. ENGINE.txt pins that
source; do not relabel earlier images as its final build.

Independent PE inspection qualified an owned 19-DLL, 11,018,734-byte file stage,
with exact source/stage hashes and no missing non-system import names. Matching
Python 3.10 metadata-domain checks prepared an isolated app-local runtime, where
actual client/server startup succeeded. This does not independently identify
every mapped provider or prove every plugin ABI. Both Windows installs still
need fresh exclusive/no-overwrite dependency placement and guarded product
installation. File closure is not public-redistribution acceptance.

The first isolated Full build failed on a missing freetype include path. A
supported, scoped make-variable correction completed the same Full entrypoint.
Its plugin prerequisite also fetched the standard ODE source archive, contrary
to that invocation's requested no-network scope. This operational deviation and
its original logs are retained; the result is a compilation pass, **not a
no-network-compliant transaction**. The later clean Full used the independently
reviewed existing-cache route: the exact ODE archive and newer cached library
satisfied their real make targets, cache identities stayed exact and no
wget/download/extract/bootstrap was observed. That is not a universal network
sandbox; top-level `-o` does not propagate to the plugin child. No player data
or dependency cache was replaced to hide the earlier event.

The generated HL2 header differed only in its generator-path banner. The exact
generated file and diff were preserved before restoring that owned banner-only
change. Its shader body was unchanged; no build product is qualified merely by
file presence.

The paired inspected QC candidate commits and engine pins are local only.
At this source checkpoint the remaining delivery work is the priority-fix
clean commit/tag-bound Full, final product/runtime binding, Windows dependency
placement, and normal guarded dual Windows/fleet deployment. No publication,
deployment or observed owner-feel pass is claimed here. Existing production /
default movement remains in service. Subsequent delivery receipts must name
actual committed source and installed hashes, not merely this checkpoint.

## Small human check after reviewed deployment

In a disposable local practice session, before starting a fresh map:

```text
sv_movementprofile ag-100
map surf_ace
```

Repeat with `ag-250`; restore `default` before a fresh map to return to normal
Source. Do not execute a map-changing check during a valued run. The optional
manual cfg is `ftesurf/cfg/test/p1542-ag-profile-manual.cfg`; it is a test input,
not proof it was executed.

Try a short walk/jump/crouch, a stair/edge, and a water/ladder transition where
available. Check plausible feet/eye height and a newly created practice save/load.
Return to default and confirm the normal save/replay list remains present and
practice remains separate/unranked. Report a small clip or map/spot rather than
resetting or deleting existing data. These checks are pending in lextest.md and
would establish only what the owner actually observes, not measured reference
parity, performance, or the missing 1000/HL2 behavior.
