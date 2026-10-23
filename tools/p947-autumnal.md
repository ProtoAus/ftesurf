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
Actual CLI wrong-predecessor and absent-map controls both refuse without changing
the generated subject. Three VMs compile with0warnings before and after preserving
published peer P946; no generated progs are deployed for this metadata-only fix.
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

Published source: QC `b296168b7225a4735024e2ca93822dd595777dcb`, engine ledger
`e236a3b60f1d47f6409f70f5083e394beb1e9637`. Both preserve published P946; native
commit/tag stay unchanged. No native/VM binary or Pi deployment.

Generated through that clean committed tool on23Oct2026:

- `C:/FTESurf/ftesurf/data/mapdeps.txt`,11:17:55Z:29766bytes,
  SHA256 `4da8d2c18523224c128c5ab7f684f0bfc1c7246414a10b3307638b141c2a35f5`.
  Exactly the native subject bytes. Its29705-byte predecessor is retained;
  removing only the added Autumnal row reproduces every original byte.
- `C:/FTEQuake/ftesurf/data/mapdeps.txt`,11:17:56Z:79bytes,
  SHA256 `9f5ac45de5adf60bb9e00ccaab2012cf94ecbc1f4c948c8981db6378cac7b7ea`.
  This cache was absent; the new file contains the native version1 header and
  only Autumnal's row. This does NOT claim a full dependency-catalogue sync.

Both destination hashes read back. Protected progs/native/config/mount-list
files remain unchanged; no owner process was restarted. This is a generated
asset-cache update using the README map-data procedure, not a player-data edit.
The controlled native cold pair proves behavior; fresh owner-session appearance
still needs the check below, not a claim from hashes alone.
Human visual acceptance remains pending in lextest.md. Phantasia, Epiphany and
the Kvas/Boreas sky cuts are separate unresolved cases.
