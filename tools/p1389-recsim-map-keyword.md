# P1389 — exact ordinary map keyword ownership

## Problem and contract

The grammar over `SV_RecOpen` in `src/server/sv_timer.qc` defines `map <name>`
and permits unknown keys. The ordinary checker splits header keywords on whitespace.
`derive_leg` explicitly makes the map header authoritative when present, but intentionally
uses the canonical path when the header is genuinely absent.

Similarity's literal `startswith("map ")` dispatch missed bare `map`, `map\t`,
and leading-whitespace forms. A known header with no payload could therefore vanish
into path inference. Valid whitespace could lose the declared map. The existing
`map ` case already raised `MalformedRec`; no escaped `ValueError` was reproduced.
`compare_paths` does not filter map identity: it demonstrates whole-stream availability
and support, while `derive_leg` and census demonstrate authoritative grouping.

## Small change

Dispatch the exact whitespace-separated `map` keyword into the existing payload
check. Missing payload takes the existing malformed/null-metric path; valid tabs
and leading whitespace retain the actual header identity. Unknown `mapfoo` and
`mapper` remain unknown. A genuinely omitted map still permits path fallback.
No other header, input parser, capture, native held framing, schema, clock, selection,
threshold, enforcement, ranking or historical observations change. No native
pin/tag, VM, QC Build or recorder change. This diagnostic correction is not a
player-facing HUD/gameplay change and adds no player patch notes.

## Acting source proof

Two new methods in `tools/test_recsim_parsing.py` use the existing 80-row ordinary
fixture at canonical-looking `data/runs/path_map/main` paths. Controls verify exact
raw SHA/byte captures, 80/80 matches, prefix80/cover1 and unchanged file bytes.
Only the map header changes. Normal/absent/unknown map-like headers act as controls.
The authoritative header differs from the path; census checks the actual group and
one available pair, not a hypothetical map filter inside `compare_paths`.

The unmodified ac915 reader fails exactly five subcases: three blank known-header
forms still produce full comparisons/path fallback, and two valid whitespace forms
lose the declared map identity. The fixed reader passes all cases. Existing blank
map-space coverage remains unchanged rather than duplicated.

## Verified and limits

- Targeted methods: numeric13 + opportunities6 + parsing12 = **31 passed**, including
  all 29 unchanged methods and the two additions.
- Adjacent controls: limits3, source capture4, unreadable4, held readers15 all pass;
  held metadata24 methods complete with one existing environment-dependent skip.
- `python tools/test_reccheck.py`: **949 checks, zero failures**.
- Read-only runs-only CLI sweep: **554 recordings, 168 paired views, 351 existing
  faults** before and after. Exact CLI output and all 722 input files' SHA/length
  inventories agree. This checker does not import recsim, so the sweep is regression
  evidence only; the acted counterfactual is the correction proof.
- Python compilation and diff whitespace check pass. No engine/QC build is needed
  for this Python-only change. LSP diagnostics were unavailable in the source worker;
  source execution/compilation is not represented as an LSP pass.

Source verification only; no deployment or native replay claim, no tier/cutoff
credit, no corpus repair/regrade. Separate previously qualified source and delivery
packets remain unchanged and are not requalified by these tests.
