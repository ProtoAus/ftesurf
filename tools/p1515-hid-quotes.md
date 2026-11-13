# P1515 — decode native cvar quoting before checking input identity

## Problem / change

The HID reader did not invert the default native `COM_QuotedString` encoding.
An escaped cvar could therefore be read with a different integer truth/scale and
produce a false angle-identity finding. Plain quoted backslashes were incorrectly
consumed as escapes; header/change preprocessing collapsed value whitespace.

The reader now distinguishes ordinary quotes (literal backslashes) from the
backslash-prefixed escaped form, preserves quoted payload whitespace, and reports
malformed quoted values as file-format faults. A malformed change invalidates its
known identity constant until a valid update; it cannot reuse a stale sign/scale
to accuse later mouse frames. Valid wrong-sign controls still fault.

Python reader/tests only. No movement, native writer, journal grammar/schema,
capture, calibrated threshold, ranking rule or QC Build change. This does NOT
attest physical input, solve legacy producer truncation, model an unrecorded
non-default console codec, or regrade historical player data.

## Actual qualification

- Literal production `COM_QuotedString` from native622268893 compiled and ran:
  **16 matching rows** over8 fixed cvar values at both real64/128-byte capacities,
  compiler exit0/zero warnings. No native producer change/full build was needed.
  A direct compiler launch without the supported UCRT PATH/TMP environment
  produced no usable result; retained, then the supported environment completed.
- New fixtures against the untouched parent reader fail **32 checks**. Fixed
  reader suite: **378 checks,0 failures** on Windows and ARM Python, including
  **64 new assertions**. Positive whole journals actually judge nonzero mouse
  input; wrong-sign controls still report angle failure. An invalid change has
  exactly8 unknown transitions, then the valid update resumes judging (21 total).
- Actual reader CLI: clean escaped-value journal exit0/zero faulty files;
  wrong-sign control exit1 with `YAW IDENTITY BROKEN`. Default clean CLI output
  is terse: do not infer a missing exact-identity field from its absence. The
  first over-specific output reader failed; retained stdout is authoritative.
- Receipt checker **268/0**; recording checker **949/0**.
- Existing **136 HID files**, same acquired bytes for parent/subject: unchanged
  fault lists and **3 faulty** files. No player file writes or historical regrade.
- Required runs corpus: **568REC +183VIEW**, identical hashes/results; existing
  **349REC/7VIEW faulty** unchanged. This is parity, not a fault-free corpus.
- Supported product QC `src/build.ps1 -NoDeploy` verifies current metadata;
  results/provenance are retained separately from reader acceptance.

## Remaining limits / delivery

The writer still clips long header/change cvar strings to its existing buffers.
A decoder cannot reconstruct missing suffixes; the remaining backlog names that
separate issue. `dpcompat_console` selects another encoding that is not recorded
in these journals; no effective-value guarantee is inferred for that profile.

Independent frozen-source reviews and normal guarded deployment remain separate
from implementation/source publication. The shared installed reader has peer
edits and was not overwritten. No install, lobby/backend, player data/config,
service or owner process changed during this offline qualification. Native
commit/tag pins and QC Build remain unchanged for this Python-only patch.
