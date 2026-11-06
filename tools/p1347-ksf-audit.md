# P1347 KSF coverage, Fetch KSF and gentler replay retries

## Status — acquisition is still running

Catalogue verified **2026-11-06T13:11:35Z**; coverage snapshot **2026-11-06T13:34:30Z**.
The full current provider list returned 955 maps, including
**33 tier 7 and 10 tier 8 maps**. All 43 are installed. Fresh tier/course metadata
matched the prior high-tier scope: **1,348 main/stage/bonus × direction boards**,
including FW, SW, HSW and BW. Secondary styles are explicitly queried even when
that style's main board is empty. The accumulated local catalogue retains one
historical name absent from this provider pass; it was not purged.

Baseline **2026-11-06T10:19:20Z**; both columns use the same count definitions.

| Measure | Before | Snapshot |
|---|---:|---:|
| Boards walked to their end | 236 | 1,167 / 1,348 |
| Valid cached board times | 26,569 | 39,715 |
| Held database times | 26,613 | 39,759 |
| Upstream replay advertisements | 2,291 | 4,280 |
| Ready, current-bound replay entries | 718 | 1,160 |

Held rows and cached rows differ because earlier imports remain preserved; they
are not two counts to add. A ready replay entry requires the ordinary current-row
and actual file checks, not merely a database replay ID. This is not a watch-through of every
replay or proof of geometry/feel. KSF does not advertise a replay for every time.

At this snapshot the remaining replay advertisements are **2,959 pending**,
**143 not currently bound**, **13 conversion-deferred** and
**5 otherwise deferred**. No board is set aside. Of the unbound candidates,
75 still have an eligible source-binding refresh due and
68 are already within the ordinary refresh deferral.
These are gaps, never successful acquisitions. Conversion, PB authority and genuine
upstream refusal checks were not relaxed to make the counts pass.

The owned bounded worker is **still running**, filling times and attempting eligible
advertised replays. Each batch releases admission and the shared cache lock;
real parks remain binding. Completion means all currently eligible work is
accounted for, with unavailable/deferred cases reported separately, not that every
advertised replay was acquired. Live aggregate output remains `latest.json` under
the owned `ksf78-20261106T1020Z` task root; no player identities are in that report.

## Per-map snapshot

`Times` is valid cached board rows. `Replays` is ready/current-bound entries versus
upstream advertisements across every category, not main-course replays alone.

| Map | KSF tier | Complete boards | Times | Replays |
|---|---:|---:|---:|---:|
| surf_antagonist | 7 | 22/28 | 847 | 96/119 |
| surf_antagonist2 | 8 | 43/48 | 627 | 12/126 |
| surf_anubis_ksf | 8 | 45/52 | 850 | 0/163 |
| surf_blackheart | 7 | 16/16 | 154 | 24/33 |
| surf_corruption | 8 | 22/28 | 646 | 36/111 |
| surf_deity_ksf | 8 | 23/24 | 379 | 39/54 |
| surf_devil | 7 | 19/24 | 729 | 58/90 |
| surf_doomsday | 8 | 25/28 | 513 | 24/55 |
| surf_dune | 7 | 55/56 | 1,239 | 52/147 |
| surf_exonic | 7 | 14/16 | 279 | 4/26 |
| surf_gigapede | 7 | 26/28 | 456 | 65/81 |
| surf_goliath | 7 | 28/36 | 783 | 58/121 |
| surf_hades2 | 7 | 48/48 | 14,555 | 165/377 |
| surf_hardline | 7 | 34/40 | 776 | 74/121 |
| surf_helljumper | 7 | 19/24 | 501 | 0/115 |
| surf_joutsenlaulu | 8 | 17/20 | 343 | 41/47 |
| surf_not_so_prosurf | 7 | 59/72 | 1,346 | 30/217 |
| surf_nsz_fix | 7 | 23/28 | 532 | 16/110 |
| surf_null | 8 | 22/24 | 374 | 39/73 |
| surf_offskill | 7 | 20/24 | 450 | 11/71 |
| surf_olivia | 7 | 19/24 | 504 | 0/103 |
| surf_original | 7 | 7/8 | 179 | 5/20 |
| surf_pls | 7 | 34/44 | 917 | 10/156 |
| surf_prosurf | 7 | 37/44 | 943 | 61/119 |
| surf_raphaello | 7 | 10/12 | 237 | 15/34 |
| surf_ruse | 7 | 63/68 | 990 | 9/187 |
| surf_shade | 7 | 26/32 | 652 | 0/105 |
| surf_shibboleth | 7 | 52/64 | 1,140 | 9/165 |
| surf_shodan | 7 | 37/44 | 854 | 21/172 |
| surf_sidistic | 7 | 4/4 | 36 | 9/9 |
| surf_silent | 7 | 7/8 | 141 | 2/24 |
| surf_sinsane2 | 8 | 20/20 | 221 | 0/39 |
| surf_sirena | 8 | 34/36 | 503 | 0/65 |
| surf_spectra | 7 | 10/12 | 435 | 38/42 |
| surf_starvald | 7 | 20/20 | 248 | 3/41 |
| surf_techslop | 7 | 31/36 | 694 | 0/107 |
| surf_tensor2 | 8 | 49/60 | 1,430 | 81/151 |
| surf_topology | 7 | 42/44 | 586 | 7/102 |
| surf_twist | 7 | 11/12 | 209 | 0/35 |
| surf_vacant | 7 | 11/12 | 301 | 0/48 |
| surf_vast | 7 | 22/28 | 805 | 6/101 |
| surf_whynot2 | 7 | 10/12 | 356 | 40/40 |
| surf_zen2 | 7 | 31/40 | 955 | 0/158 |

## Selected-board fetch

The in-game KSF leaderboard and local map-menu leaderboard now have a visible
**Fetch KSF** button. It queues the selected course and direction through the
existing bounded **+100 times** request and normal replay-interest path. It is
asynchronous, not a synchronous scrape or promise of a replay. Ranked/non-KSF and
segmented categories do not show it; narrow menu layouts use a separate row.

## Replay retry policy

- Normal replay-worker spacing is now six seconds, with slower recovery probes.
- Missing 404/410 files are deferred individually; they do not accumulate host failures.
- Repeated 500/broken bodies and other 5xx use a **replay-only** 60-second exponential
  backoff, capped at 30 minutes. An HTTP 500 is not evidence of rate limiting.
- Real 429/access refusals retain the existing host-wide exponential protection.
  Retry-After seconds and HTTP dates are honored; pre-existing active parks were
  neither shortened nor cleared. This cannot guarantee KSF will never throttle.

## Source, validation and delivery

- Main feature `ee34da56`, inspected integrated source
  `53b94a926f2a0089cb20e3b5b21808e61fd70a79`; backend activated
  **2026-11-06T11:24:42Z**, Windows UI deployed. Current-data rollback paths are
  recorded in [surfd-generation-p996.md](surfd-generation-p996.md).
- Pi client-only compatibility component
  `5cb18943ca0071f2d85776c389dff58459453cbd`, published on `pi-p1347-ksf`.
  Its native/SSQC/server/shared/TAS path is preserved; only the client fetch feature
  and patch label differ from its inspected compatibility baseline.
- Actual `src/build.ps1 -Jobs 8 -NoDeploy`: all three VMs, zero warnings with
  qualified compiler `c24ede65`. Existing older-compiler warnings were reproduced,
  then eliminated using the qualified compiler, not waived.
- Replay-importer suite: **84 tests pass on Windows and Linux**. Top-up suite:
  **8 tests pass**. Actual pointer tests in both VMs sent style-isolated POST 202
  requests, persisted their intended queues, exercised all four direction reads,
  hid unsupported controls and checked wide/narrow geometry. Screenshots inspected.
- Both Windows installs: **8 UI/symbol destinations**, paired `.prev` files and
  protected non-targets verified. Native/plugin/SSQC/config/player data not replaced.
- All **12 lobbies**: chat warning and 10-second grace, CSQC-only swap/restart,
  none skipped. Completion **2026-11-06T12:27:00Z**; 48,122 prior protected entries
  unchanged, six new files preserved. Eight recorder parts and 183 resume files
  independently archived and verified on/off box; capacities restored, no gate left.
- Fresh installed-native client, no local CSQC/cache, downloaded the exact served
  Pi component and drew the scoreboard: exit 0, no QC error, zero smoke failures.
  Screenshot inspected: empty/no-zone `surf_kitsune`, terms unaccepted. This is
  served-code/render evidence, **not** a populated live KSF click, geometry, owner
  consent, playback acceptance or a performance measurement.
- No converter/recording/ranking/schema/native pin/tag/Build or release change.
  Newer published peer P1348/P1349 work was not built or deployed by this task.

Small human usability acceptance remains **pending**, not confirmed; see
[`lextest.md`](../lextest.md). Source, deployed code and ongoing acquisition are
separate states. Raw provider identities, private preservation material and native
fixture logs are intentionally absent from this public report.
