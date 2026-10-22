# P931 compatible fleet candidate

## Scope and provenance

This is a deployment-source variant, not a rollback of mainline or a new product
patch. Parent `26070cea2ff0f72d892b95b7b7e5cefa1a49880d` is the inspected P922
fleet baseline. Only the owned source hunks from P924 (`78bb485a`), P926
(`0d3f0e67`), P927 (`cc49836f`) and P931
(`4f20fcefa606fad44e924f5670a3af5cd805e926`) were applied. Mainline is unchanged.
The two merge-context conflicts retain the P922 callbacks, adding only P924's
phase metadata; they do not import the independently held P923 producer code.

SSQC's existing FTESURF-REC13 writer, recorder/counter/held policy and native
producer generation are retained. The sv_timer diff only adds the phase-stat
fields and their string cleanup. No native server interface, reader, evidence
schema, qualification, coverage or backend gate is changed. The P924 native pin
is required on the CLIENT for conveyor prediction; this candidate does not ship
or qualify a new lobby native. It does not satisfy or bypass the separate
mainline producer-promotion requirements.

Read-only production checks on 22 October 2026 UTC matched the published P922
receipt exactly:

- qwprogs.dat: `5fb0afc76d19b2f692d0429dbd952cf2ea7e6094acc152e7a8062fa4fb81675e`
- csprogs.dat: `9c79d9856e52b52eca4ad61ca59869b27f7e504f5cebb01dbbdbb5731e3234b9`

## Acting verification

Standard isolated build.ps1 -NoDeploy compiles all three VMs with zero warnings.
The dedicated control uses retained P918 fteqwsv64 and its matching HL2 plugin;
the client is the actual newly installed C:\FTESurf executable and its matching
P924 plugin. Module paths were read from both live processes, not inferred from
PATH. Both ends receive this candidate's progs.

On parc_colore's real567-unit belt, the body moves along it and steps off with
no subsequent correction above.25 after its intentional zone-goto. Turning
cl_triggers0 off supplies an acting missing-prediction control while the server
continues carrying: seven additional8.51..25.52-unit corrections. Restoring1
returns to zero subsequent corrections. The first correction in each arm is
bound to that arm's explicit zone-goto and printed destination body, not ignored
by an arbitrary error-size threshold. The initial size-based classifier wrongly
counted a371-unit placement correction; its reader was corrected without
changing product code or repeating passed actors.

Glock selection, actual authoritative shot sequence1, mounted model and
@glock_firesingle animation also ACT on the legacy server. Existing mainline
feature-specific controls remain separate evidence. This compatibility check is
not a new native-recording or leaderboard qualification, an audible-device test,
or owner feel acceptance. All owned processes stopped; rig configs/data were
unchanged and cl_triggers was restored to1.

Qualified candidate SHA256s:

- qwprogs.dat: `e7c8a66432a057b6db3ca18255663e151aafbbacfc2f12c59edf3e629049f836`
- csprogs.dat: `11701c87e8a40cce39acf05279d0633f81ce1876bd3a6b2b5d48146efbd29bc5`
- menu.dat: `9e2aba1c943fc0003b401dc35db6e29d9d67fe590e14ae038cef81ca1dabaf3c`

## Delivery boundary

The earlier one-player boundary was respected. Once the fleet became empty,
standard build.ps1 -Pi from clean2ec1792344e9fc63eebebdf67530590a9713c083
rechecked all12rows/zero players, compiled0/0/0 warnings, uploaded/hash-checked
both .new files, preserved .prev and restarted all12active units. Postflight at
**2026-10-22 17:59:00 UTC** found the exact qualified pair above, exact prior
P922 pair in .prev,12new PIDs and unchanged executable/mapped-HL2 hashes.
All546configuration hashes and all27722pre-existing data-path sizes/mtimes
were unchanged immediately after restart;6new data paths were present. This is
metadata preservation, not a claim to have hashed every recording's contents.

A cold-cache installed Windows client then joined live Open Lobby #12/agtricks.
The candidate cache file was parked only in the owned fixture, never a shared
install. The new csprogsvers/e6c1bb7e.dat download SHA256 matches11701c87...
above. After CSQC was actually ready, the real server selected Glock8, advanced
shot sequence1 and the client reported ready1/@glock_firesingle with positive
duration. The first too-early echo was not acceptance. Own client quit normally;
the original cache was restored with exact-hash ownership checks. No acceptance
commands were issued; no recording/leaderboard qualification is claimed.

No force, new native/producer promotion, collection activation or maintenance
gate was used. Windows retains its separately verified newer mainline/P932
bundle, not this compatibility variant. Native/held policy remains unchanged.
