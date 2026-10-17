# P755 — Steam pictures kept on disk and drawn at once

## What was wrong (read in the code and the owner's cache, 2026-10-17)

P715's disk cache (`cl_steampic.qc`) did keep pictures, three ways badly:

- **A copy was good for one UTC day.** The header carries the day it was written
  and a load compared it with today, so every picture was fetched again from
  11:00 AEDT. The owner's `data/cache/steampic` held stamps of 15, 16 and 17 Oct.
- **A disk copy waited its turn like a request.** `SteamPic_Frame` took one mark
  per `SP_GAP` (1.5 s), disk or HTTP, and nothing while a request was out; a CSQC
  VM starts empty every map. Thirteen pictures on a board took ~20 s from disk.
- **256 two-hex buckets.** Two marks sharing a key prefix evicted each other.

## Change (client QC only)

- One file per origin+mark SHA256 (`cache/steampic/<key>.txt`). A copy is drawn
  up to `SP_DISKDAYS` (30) days old; one from an earlier day is drawn at once and
  refreshed by a paced ask (`SP_OLD` -> `SP_FRESH`), which keeps it on screen if
  the refresh fails. P715 bucket files are still read, never written.
- Disk copies load `SP_DISKBURST` (4) a frame, before and regardless of the ask
  pacing, the in-flight request, the strike count and `_steampic_hold`. Only
  asks stay paced, and none goes out while marks still wait for the disk.
- Validation and upload moved into `SP_Upload`, shared by disk and HTTP; the
  `SteamPic_Draw`/`SteamPic_Of` contract is unchanged.
