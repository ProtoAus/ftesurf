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
- The earlier candidate pin7 arm refused because its world could not state the
  required zone pin. Its paired baseline arm was not launched. The exact
  missing maps/ zone input has since been matched to retained successful
  Windows evidence, but new input admission and actual legacy completion remain
  gated. The old failure has not been regraded and overall acceptance is not
  complete.

## Build and delivery limits still open

The engine source is frozen locally at
`1bfa3eae138c70ad94e05416dfd96fc0cb327cb4`, tag `patch-1542`; it includes the
published P1541 delivery-note advance and a portable plugin-metadata emitter
correction. It is not pushed. The earlier clean `92d87c1f2` Full cohort compiled
with the exact `git-8734-patch-1542-0-g92d87c1f2` stamp and no new warnings, but
its five plugin ZIP payloads contain inherited literal backslash-n separators.
Those original products remain retained with a metadata HOLD, not rewritten.
Five old-echo negative controls and five same-shell printf positives verify the
one-line emitter correction at the source/byte level; they do not execute the
package parser. A new source/tag-bound Full is still required before qualifying
the corrected products. The former unpublished local tag object is preserved;
no public tag or history was replaced. Independent PE inspection has qualified
an owned 19-DLL, 11,018,734-byte file stage, with exact source/stage hashes and no
missing non-system import names. Both Windows installs still lack those exact
app-local names. Final product binding, fresh exclusive/no-overwrite placement
and an actual loader/runtime check remain required. File closure is not ABI or
public-redistribution acceptance.

The first isolated Full build failed on a missing freetype include path. A
supported, scoped make-variable correction completed the same Full entrypoint.
Its plugin prerequisite also fetched the standard ODE source archive, contrary
to that invocation's requested no-network scope. This operational deviation and
its original logs are retained; the result is a compilation pass, **not a
no-network-compliant transaction**. The next ordinary `-Engine` build has an independently reviewed existing-cache
route: the exact ODE archive and newer cached library satisfy their real make
targets. No-wget is a prediction to check at execution, not an already observed
pass or universal network sandbox; top-level `-o` is not propagated to the plugin
child. No existing player data or dependency cache was replaced to hide the event.

The generated HL2 header differed only in its generator-path banner. The exact
generated file and diff were preserved before restoring that owned banner-only
change. Its shader body was unchanged; no build product is qualified merely by
file presence.

The paired inspected QC candidate commits and engine pins are local only.
Remaining delivery work includes the corrected commit-bound Full and actual
runtime checks, the outstanding historical input qualification, final Windows
dependency placement, and the normal guarded dual Windows/fleet deployment. No publication, deployment or observed owner-feel pass
is claimed here. Existing production/default movement remains in service.

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
