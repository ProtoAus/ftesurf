# P947 — Autumnal optional-content metadata

Claimed after fetching both repositories on 23 Oct 2026; inspected public patch
headings and untracked pNNN files through P946. No engine/native change intended.

Problem: the installed generated dependency catalogue lacks bhop_autumnal's
CS:GO Source 1 dependency. The actual Momentum BSP references
`blacktop_ext_01`; the installed Legacy pack provides it. A private native actor
with that optional pack mounted renders the concrete and blacktop surfaces.
The later cold native pair below proves the ordinary base-mount path.

Plan/falsifier: use the existing mapdeps generator to update only the scanned
map's rows, preserving every unrelated byte and requiring the existing file's
SHA256. Preview must write nothing. Missing-map and wrong-predecessor controls
must refuse. A cold native client with the ordinary base mounts must initially
miss the surface, then the generated row must cause fs_automount to consume the
optional pack and restore the same surface. Do not change the owner's mount list,
config, keys, saves or recorder consent. No new always-mounted game pack.

## Implemented and verified

`tools/mapdeps.py --map bhop_autumnal --update-map --output <catalogue>` repairs
only the scanned map's rows. An existing output requires
`--expected-sha256 <inspected-digest>`; `--dry` never writes. New outputs start
with the existing native version1 header. No new protocol or scanner namespace.
The scanner's configured mounted-directory inventory is unchanged; this is not
an all-package/native-winner resolver for arbitrary aliases. Autumnal's actual
winner was separately checked as the Momentum BSP.

Six `tools/test_mapdeps_update.py` cases pass under Python normal and `-O`:
space-bearing specs/unrelated CRLF bytes, duplicate replacement/removal,
wrong/missing predecessor refusal, creation/idempotence, bad header/name/spec,
and an ACTED failed replacement preserving the old file and cleaning its temp.
Actual CLI preview left the source bytes exact; actual update added only
`dep bhop_autumnal steam:Counter-Strike Global Offensive/csgo`.
These are trusted local generated-file checks, not a cross-process CAS,
hostile-path or power-loss guarantee.

Cold native control/subject on23Oct2026 used the same installed client/progs,
three ordinary base mounts, explicit fs_automount1 and normal lighting/visibility
(fullbright/drawflat/novis0). Same body8608/6112/128, aim0/0, zero velocity.
Control reproduces checkerboard platform tops and missing blacktop VTF.
Subject logs the map's automatic dependency, consumes the Source1 archive,
reports blacktop loaded512x512 BC1_RGB, and screenshots visibly restore the
blacktop tops/foreground. Only the generated metadata varied. Optional luma/
normal fallback lookups remain; no claim that every missing report is repaired.
No terms acceptance, ranked run or submission. Both actors exit0; four owned
content junctions removed and both owned fixture input files restored exactly.

The first startup fixture had no active gameplay and is a failure, not a control.
Explicit manifest/post-init barriers recovered real worlds. A separate cold-pair
preflight wrongly counted a commented mount, refused before mutation, then the
same active-line classification seam was corrected. No live failed transaction
was bypassed and neither failure is feature acceptance.

## Delivery

Pending source publication and dual Windows generated-catalogue delivery.
No native/VM binary, persistent mount list, owner config/keys/saves or Pi swap.
Human visual acceptance remains pending in lextest.md. Phantasia, Epiphany and
the Kvas/Boreas sky cuts are separate unresolved cases.
