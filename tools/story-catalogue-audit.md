# Story/Event catalogue audit and calibration

Static aggregate snapshot: `tools/story-groups.json`, public `/api/board?groups=<exact-map>&style=clean`, response epochs 1795065419–1795065520 (2026-11-19 UTC). No player rows were fetched for this audit. `src` and `x` are the backend's selected imported source and positive-time count for this course, **not** Momentum+KSF combined population or proof of complete upstream coverage. Geometry/course identity remains the exact catalogue map and track. In particular `surf_autumn_fix` uses the exact KSF fixed build; no general `_fix` stripping/equivalence is introduced. Existing backend family-reference policy is unchanged.

## Policy and refresh

Ordinary Story bronze requires a full finish. Silver is the snapshot's actual G4 boundary (`ms[4]`); gold is G2 (`ms[2]`). Story `time` is strict-under, so each target is **boundary + 1 ms**: the exact group boundary and ties qualify. No WR multipliers, estimated stage sums, invented distinct tiers or whole-second rounding.

The 96 occupied Story slots now have 96 full-finish bronze criteria and 95 calibrated silver/gold pairs. `surf_sinister` has no aggregate group ladder and remains finish-only. `surf_joutsenlaulu` has only 20 imported KSF rows: G2 and G4 both equal 257164 ms, so both cutoffs honestly equal 4:17.165. There is no separately evidenced silver difficulty there. All other snapshot gold boundaries are strictly faster than silver. All catalogue times are finite positive milliseconds.

Refresh is **explicit**, not automatic moving targets:

```
python tools/story_groups.py --output <reviewed-snapshot.json>
# Inspect geometry identity, source/count, absent/collapsed boundaries and diffs first.
python tools/story_groups.py --apply-snapshot <reviewed-snapshot.json>
python tools/test_remaining_requests.py
# Run surfd/test_story.py and surfd/test_groups.py in the documented test environment.
```

The tool only rewrites ordinary Story medal lines; occupied courses, Events, historical Halloween, level order and explicit chapter gates are preserved. The shipped snapshot is a reviewed calibration, not a promise of current live G2/G4 membership. Future refreshes change static targets and require review. No timer, recorder, run-evidence or award-calculation semantics changed here.

## Requested additions

Previously empty stable slots (one-based):

| Story slot | Exact map | Source / count | G2 boundary ms | G4 boundary ms |
|---:|---|---|---:|---:|
|32|surf_fuchnut|KSF /169|40065|40614|
|35|surf_despair|KSF /289|58616|60484|
|37|surf_centipedes|KSF /210|75211|77748|
|64|surf_shape|KSF /990|40797|41974|
|68|surf_remeanian|KSF /64|71804|73200|
|69|surf_autumn_fix|KSF /649|73680|75851|
|70|surf_ferros|Momentum /1450|42300|43605|
|80|surf_highlands|Momentum /554|127635|238185|

Chapter headings containing mixed-tier additions are neutral `Chapter N`, rather than falsely advertising their old tier band. Occupied indices, Story59's reservation, explicit unlock bars and chapter order are unchanged; the gate reachability test retains fixed early gates and checks every later gate is achievable from preceding available medals.

Events remain gold-only completion tasks: slots 3 `surf_autosave`, 5 `surf_gary_barlow`, 9 `surf_nightingale bonus 4`, 12 `surf_nightingale bonus 5`. Autosave/Gary main-course group evidence is also retained in the snapshot, but no timed Event medals were invented.

Nightingale B4/B5 are **pending owner zones**, not playable now. Opt-in `course zones` checks first effective local, Momentum-local, then online zone JSON, requiring the exact bonus's start and finish regions. An existing main-only higher-priority file blocks lower-priority bonuses; unreadable/malformed/missing geometry fails closed. This only controls `timed`/Play availability and available gate capacity: previous awarded credit remains calculated/visible. Checks run once per opted-in course per Story recomputation, not per player. The Story cache is stale-while-revalidate: after its 60-second TTL, the next request queues refresh, and new availability appears when that asynchronous refresh finishes. Both backend and menu already use `timed=0` to show `no zones yet` and withhold Play. Publishing a correct lower-priority file is insufficient if a higher-priority main-only override remains effective.

## Existing issues deliberately preserved for owner policy

- Event `surf_voyager` (`via other`) and `surf_fiellu bonus 4` (`via ramp`) have no authored spots. They remain undecidable; no fabricated route positions or substitute awards.
- `surf_kvas bonus 4` occupies Events77 and85. Both stable credit-bearing slots remain; do not silently remove duplicate awarded credit.
- Zoomathon's legacy max-fog Event still uses finish-only credit pending owner policy. Historical dated Halloween challenges are not converted into current progression.
- Imported bonus rows do not prove playable lobby geometry. Requested Nightingale courses are explicitly gated. Other existing course/zone coverage gaps remain an operational audit/manual check, not a reason to fabricate targets or rewrite established credits.
- Existing Story comments that say `unzoned` are historical observations, not measured current course availability. No live catalogue promotion, deployment, private player-data inspection or owner zone changes performed.

## Validation limits

Offline catalogue parser/threshold tests prove exact milliseconds, snapshot match, fixed roster, bronze full finishes and gate capacity. Synthetic backend tests prove course override precedence, absent/malformed/unreadable zones, automatic availability re-evaluation at cache refresh, and retained credit while unavailable. They do not prove geometry is surfable, that a live lobby/backend serves matching zone files, or rendered menu/HUD correctness. Those remain explicit runtime/owner checks.
