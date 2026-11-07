# P1370 — start the existing prefix at the aligned overlap

Source/test acceptance only at this boundary, not installation or live delivery.
The unpublished working draft used number1369; concurrent published map metadata
claimed that number before this feature was published. Its history is preserved;
this feature uses only1370. The validated source/test bytes did not change and no
result was rerun, regraded or renamed to obtain acceptance.

## Problem and change

`best_offset` already skips leading rows outside a negative row alignment. Its
first comparison is then `a[-d], b[0]`. `prefix_len`, documented as the exact
common run **from the aligned start**, instead began with negative `j` and exited
immediately. A genuine79/79 agreement could therefore have reported prefix0 and
cover0 solely because this pair was presented in the negative-offset direction.

Start `prefix_len` at `max(0,-d), max(0,d)`, the first overlapping pair. Continue
to stop at its first mismatch and divide the prefix by the longer run. Offset
selection, first-best tie handling, match/support counts, minimum length, parsing,
source budgets/capture and existing zero/unavailable distinctions are unchanged.
This does not promise general orientation invariance of offset selection under ties.

No new statistic, source signal, schema, threshold, ranking, default enforcement,
recording grammar/clock support, native pin/tag, VM or QC Build is introduced.
Stored observations/history are not rewritten, repaired or remeasured.

## Acting controls and subject

The existing ordinaryREC9 fixture contains80 distinct commands. Exact distinct-file
control performs80 real comparisons with prefix80/cover1. Shift B's commands one
row ahead while preserving row count/header/clocks. Both orientations must perform
79 actual comparisons, agree79/79 and select offsets+1/-1; raw SHA/byte capture,
source lengths and unchanged buffers are asserted **before** prefix/cover.

- Perfect overlap: both directions prefix79 and cover79/80.
- First mismatch at overlap row40: agreement78/79 in both directions, prefix40,
  cover40/80. This proves first-contiguous-run semantics, not a longest-match count.
- Direct no-overlap bounds at offsets-81,-80,+80,+81 remain prefix0.
- Exact frozen predecessor BF99: the same new acting testcase fails only the two
  negative-offset prefix subtests; positives/capture/offset/support pass.
- Fixed subject: all six existing Opportunities cases pass on Windows Python3.10
  and actual ARM Python3.11.2/aarch64. Both platforms reproduce the exact two
  predecessor subfailures, not import/setup errors. No metric is mocked by this case.

Independent source review CLEAR; no MUSTFIX. Small source-only ARM overlays contain
no player data/application. Bounded children are reaped, owned tmp is empty and
cache prefix absent. Windows standalone tests' three owned test.db-only fixture
homes were inventoried and individually retired; no other data was cleaned up.

## Existing banks and corpus

Windows all36 actual child programs return0:
- Five recsim programs:25 unittest cases pass, no skips.
- Thirty existing similarity programs:273 unittest cases,267 passes/six established
  Windows skips, plus68 standalone checks. Skips are four missing SQLite result-code
  attributes and two POSIX ownership/FIFO controls, not claimed passes.
- Reader executable:949 checks, zero failures.

The new reader/corpus checks use current checkerA221c7ee, not the earlier deployed
frozen3eab465a; no checker was shipped by these tests. Same554REC+178VIEW=732 files,
zeroPART, exact input domain and raw bytes before/after. One actual checker sweep
of564 explicit primary/standalone-view inputs (paired views included by its CLI)
returns1 for the same351 pre-existing faults:344REC and sevenVIEW. All732 per-file
report blocks match the prior output as a trailing-whitespace-normalized multiset.
No fault-content increase, input omission, corpus repair or regrading is claimed.

The771-Python-file source domain/raw bytes remained exact through validation.
Publication metadata and concurrent mapcfg changes do not alter those dependencies.
No new warning or failing product testcase is introduced.

## Limits and delivery

These are controlled old-format ordinary fixtures, not genuine/current-mode client
coverage or a calibration corpus. No calibrated cheat cutoff, identity/authenticity,
hardware origin, new enforcement, resource bound, whole-history freshness, UI/manual
acceptance, actual namespace/current-data cutover or whole-fleet credit follows.

P1368's separate guarded generation/owner authorization is not implied by this
reader fix. Any helper installation must preserve the inspected current tuple,
player data and stored observations, use the existing guarded reader procedure,
and record actual destination hashes/default-caller behavior separately. Source
publication is not deployment.

### Windows delivery — 7 Nov2026,12:11UTC

The exact clean inspected source6848f729 was installed by the existing Windows
reader transaction, narrowed to this ONE file in BOTH `C:/FTESurf/tools/census/`
and `C:/FTEQuake/tools/census/`. Destination bytes equal source15e19bf4. Both exact
BF99 preimages are retained with original timestamps/ACL; replacement ACL and
source-path index stayed unchanged. No native/game process, configuration, player
data, other source, checker or metadata helper was changed.

Actual installed paths each passed13 numeric-reader cases plus all six Opportunities
cases, not just a working-tree source rerun. Absent private bytecode prefix plus-B
prevents stale-cache selection; both owned fixture tmp roots are empty afterward.
Checker3eab465a and heldmetaA3f73a0c remained exact in both installs. This19-case
per-install proof is distinct from the current-checkerA221 bank/corpus above.

NanoPi installation of this reader is **not claimed**. It remains serialized after
P1368's actual owner cutover output/current proof and a freshly bound reader plan.
These Windows explicit-path checks do not establish default backend namespace,
Linux installation, genuine/current-mode coverage or whole-fleet acceptance.
