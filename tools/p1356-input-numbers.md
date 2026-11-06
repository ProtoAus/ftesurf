# P1356 -- reject non-native numeric spellings in required input fields

## Problem

Python numeric conversion accepts spellings that the recording input grammar does
not supply. The partial similarity reader could silently turn such required
fields into ordinary moves. The full recording checker could likewise report no
fault for a malformed numeric payload in an otherwise clean grammar fixture.

The actual untreated similarity reader measured all15 ASCII mutation arms as
match1.0 with80 opportunities. An independent unequal control measured0 with76
opportunities. The existing full-checker REC9 builder produced a clean80-input
control;33 numeric-token mutations also incorrectly retained zero faults/80inputs.
These are synthetic reader observations, not native replay or source-authenticity
proof and not evidence about any real player's behavior.

## Change

- Similarity checks only its existing required move-tick, movement and button
  tokens for ASCII numeric spelling without Python digit separators, before its
  existing conversions. A malformed required row makes the WHOLE stream
  unavailable; it cannot become a measured prefix, zero score or clean sample.
- The full recording checker applies that admission check only to the existing
  ordinary `in`/`fzin` numeric payload, before its existing integer/finite-float
  checks. A bad row retains the existing numeric-fault handling.
- Preserve the similarity reader's deliberate `int(float(token))` fractional
  truncation, ASCII signs and exponents. The full checker retains its different
  pre-existing integer/float and precision rules; this does not waive its existing
  angle-exponent diagnostic. Its `is_int` helper is not a drop-in substitute:
  that helper rejects plus signs and imposes a separate length restriction.

No global float/header/optional-field change, expanded clock model, capture or
recording format/API, schema, historical rewrite/retry, threshold/calibration,
identity, verdict policy, badge/ranking, backend runtime source, native pin/tag,
VM or QC Build change. Partial similarity parsing is STILL not full-file grammar
validation or recording authenticity. Other malformed-field classes remain
outside this narrow change.

## Verified source

- New9 test methods pass. The untreated Windows reader/checker fail98 assertions;
  one additional ACTED prior-reader-to-unchanged-collector integration fails too.
  The real collector previously stored the bad spelling as a notable comparison;
  now it stores the existing unjudgeable `malformed` skip, not a measurement.
  Neither reader nor comparison is stubbed in that integration.
- First/middle/last positions, required columns, underscore/Unicode-digit forms,
  bounded/unbounded capture, genuine matching/unequal controls, fractional
  truncation, signs, allowed exponents, keyword whitespace and existing clock
  classification are covered. Windows legacy decoding already rejected some
  Unicode forms; those are regression controls, not falsely counted baseline reds.
- Supported13/15 contexts and frozen-release aliases retain clean controls.
  Existing native framing already rejects their corrupted ordinary payloads;
  that is not claimed as newly discovered coverage or native-engine acceptance.
- Existing partial-reader23 and recording-reader949 checks pass. Collector270 unittest cases pass
  with6 known Windows SQLite/POSIX skips. The original broad discovery imported
  a standalone program whose successful `SystemExit(0)` was reported as an import
  error; the proper unittest pattern excludes that program. Its standalone checks
  themselves passed. No unrelated product code was changed to repair the loader.
- Stable548REC/178VIEW corpus, including10 unpaired views, retains351 existing
  faults. All726 file names/bytes remain identical to the predecessor manifest
  before and after the sweep; no player data was written.
- Initial fixture assumptions about exponent acceptance and a native status field
  after earlier framing refusal were corrected before product edits. Original
  failures remain distinct from product results. LSP has no recorded diagnostics;
  that is not a native/QC build or physics claim.

## Publication and delivery

Source freeze, two independent reviews, ARM checks, both Windows reader targets
and the separately checked NanoPi helper swap are PENDING. No live behavior is
claimed by the source tests above. Deployment must preserve all84 existing backend
runtime bytes, unchanged heldmeta, both actual helper beforeimages and current-data
rollback. The canonical tools are outside the runtime84/external3 guard closure:
actual process-namespace visibility and import origins must be checked separately,
not described as guard-sealed or inferred from an injected qualification reader.
