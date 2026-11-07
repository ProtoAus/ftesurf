# P1393 — whole-file duplicate keys for the offline pairs census

## Problem and change

`tools/census/recsim.py pairs` excludes byte-identical copies before grouping
recordings. Its key was SHA-256 of only the first MiB plus file size. Different
same-size files with the same prefix were therefore omitted as duplicates before
pair acquisition; the parser could already see their different later moves.

Hash fixed-size chunks through EOF using a context-managed file. Preserve the
existing size-key suffix, OSError handling, eligibility/name filters, grouping,
sampling, minimum support, comparison metrics and printed categories.

## Acting controls

Two added methods in `tools/test_recsim_parsing.py` use bounded synthetic REC9
files containing 80 moves after an ignored padding comment larger than one MiB:

- Identical-copy control parses both 80-row streams, compares 80/80 with exact
  captured SHA/length, and exercises actual `cmd_pairs`: one duplicate, one
  retained file, zero negative pairs and one shifted-epoch positive control.
- Distinct-tail control changes exactly one equal-width movement token beyond the
  first MiB. Size/prefix remain equal, full hashes differ, and direct comparison
  acts at 79/80. Original FD90 skips one file and yields zero negative pairs;
  subject retains both, skips zero duplicates, yields one negative pair and two
  shifted-epoch positive controls. Source buffers remain unchanged.

The two-method predecessor run fails exactly the distinct-tail verdict, after
its preceding source/stream/control assertions act. Original unclosed-file
ResourceWarnings are retained; the context manager removes those warnings.
Subject full parsing14 passes with no new warnings.

## Validation and limits

- Numeric13, opportunities6, limits3, captured-source4, unreadable4 and held-reader15
  methods pass. Held metadata: 24 methods run, one existing skip.
- `python tools/test_reccheck.py`: 949 checks, zero failures. An initial 110-second
  test timeout is retained; the same entrypoint completed with adequate time.
- Read-only runs CLI: same 554 recordings and 168 paired views, identical 722 input
  buffers and summary, 351 pre-existing faults before/after. The checker does not
  import recsim; this proves no corpus fault increase, not duplicate acquisition.

This is offline diagnostic `pairs` acquisition, not a live collector change or a
claim that these synthetic files are independent human performances. It neither
calibrates a threshold nor regrades stored observations. The parser, capture,
metrics, native framing, defaults, schema and enforcement are unchanged. Separate
parse/hash/stat reads remain non-atomic. Full-file hashing adds whole-file I/O;
fixed-size chunks do not establish a whole-pass, elapsed-time or RSS ceiling.
No native pin/tag, QC Build or recording-format change. Source verification and
actual deployment are separate states; deployment provenance is recorded separately.
