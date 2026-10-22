# P930 — owner's updated Story/Event lists

## Scope and controls

Both lists have exactly 100 numbered slots, in groups of five. Empty slots stay
empty. Event 54 was omitted by the owner and remains empty. The first duplicate
Story 44 (Facility) is interpreted as 43; Story 59's combined
`Surf_Monkeys2Surf_Whoknows3` remains unassigned rather than guessing.
The repeated Kvas B4 events at 77 and 85 are intentionally both retained.

Canonical spellings checked against the live map roster include
colin_blaster_69000, aesthetic, r-ne, sandtrap2, classics3, runewords,
runewords2, runewords2_lod, starvald, joutsenlaulu and shape.
The canonical no-variant names select Momentum where present. The roster has
no Momentum source for tendies, starvald, olivia, sidistic, sinister,
antagonist2, deity_ksf, joutsenlaulu, sirena, leet_xl_beta7z,
network2008_final, fruits2, 1998, board_this, kismet and shape; these are
explicit available-build fallbacks, not claims that a different BSP is safe
for a replay. No map file or replay identity is rewritten.

Existing Story medal criteria are identical when matched by map and bonus.
New Story maps have bronze finish only, not invented time targets. Halloween
is byte-for-byte unchanged. Existing early gates are unchanged; later gates
use the existing 65% then 70% prior timed trophy policy, rounded up.

## Verified

- Baseline three-VM build.ps1 -NoDeploy -Jobs 8: all three compile, 0 warnings.
  This patch changes data/tests/docs only, so no new VM deployment is needed.
- `python -m unittest test_story`: 45 tests pass (2.095 s), including criteria,
  slots, bonus tracks, progression, reconciliation and existing API controls.
- Independent parser comparison: all 200 map/bonus positions equal the normalized
  request; all existing Story challenge dictionaries and Halloween preserved.
- `python tools/story_push.py --check --board https://play.proto.bar`: every map
  exists in the live roster; no force flag used.
- Initial suite failures were old-list assumptions (Cyberwave existed in both
  ladders, and old capacity-derived bars); changed to Zoomathon (in both new
  lists) and recalculated bars using the same policy, not by weakening assertions.

Live initial Story hash 15c610edb7cc77d488645212fddd97a512903384a2ad50dafdf98c128f4fe00c
matches published QC commit 69cf8badfbba70ea790ef9ed428987f8fa41a0b9.
It is an older published list, not an unidentified peer edit. Preserve it as a
remote pre930 backup before promotion. Promotion succeeded using story_push.py
without --force. Destination SHA256 is
3283c5845c068fa40973100ae022bab6ee3b357890ddfe3b030310741b79bf43;
the live API serves rev 3283c5845c06. Readback at 2026-10-22T17:47:21Z and
subsequent flattened-list check prove Story 100 levels/20 chapters, Events
100/20 and unchanged Halloween 11/3. Backup is
/srv/nvme/surfd/data/story.txt.pre930-20261022T1708Z.
No backend code, generation guard or progs was replaced by this data update.

## Not functional acceptance

Seven Story entries have no timing zones: stonework3, starvald, olivia,
sinister, antagonist2, deity_ksf, sirena. Seven Event entries likewise: leet,
vegetables, fruits2, 1998, mdrn, kismet, shape. They are listed but cannot earn a
finish until timing is available. Existing Voyager alternate-route and Fiellu
final-ramp tasks need authored `spot` coordinates. Max fog is explicitly not
enforced; the current event label says finish only. No owner visual/gameplay
acceptance has been claimed.

## P929 live provenance

QC dbfb66260e79be21e6bf4a6758d9e62469dba582 and engine-log-only
e1491d369b8f4717f8b6d88769f0f63a81e9c08c were pushed. At
2026-10-22T16:54:04Z all twelve live lobby configs had only their hostname
replaced, retaining exact pre929 backups. Local RCON applied each name without
restart. The backend directory readback proved all 12 Open Lobby #N names.
No map, port, process or connected player was changed. Per-file destination
SHA256 values are retained in the owned task evidence, not inferred from RCON
reply silence.
