# P1082: TAS projects

A TAS project keeps a TAS line on disk so it can be reopened after leaving the map, a
reconnect or a restart, then edited and saved again. Local servers only; refused on lobbies.

## Use

From a paused TAS attempt (see `tools/p1077-tas-timeline.md`):

- **Save project** (Timeline tab), or `tas project save [name]`. The first save makes one
  ordinary TAS save in your save list at the earliest exactly-retained tick (the project's
  *base*) and writes `data/tasproj/<map>/<name>.tasp` with every input after it. Unnamed
  projects are called `tas1`, `tas2`, ... Later saves of the same attempt keep the base and
  add the new ticks. Saving under another name forks the project (`parent` recorded).
- **Reload project**, or `tas project load <name> [checkpoint]`: loads the base save, pauses,
  and replays every input in 128-tick chunks, then reports either "reproduced every saved
  state exactly" or "DIVERGED ... at tick T". With a checkpoint name it stops there.
- **Checkpoint**, or `tas cp add <name>`: names the current tick; written by the next save.
  `tas cp list`, `tas cp del <name>`.
- `tas project list`, `tas project diff <a> <b>` (differing ticks and the first one),
  `tas project status`, `tas project close` (detach; files are kept).

## What is and is not exact

- Inputs are stored exactly: one per tick from the recording's own `in` rows (the rewind
  ring samples once per packet and has gaps), spot-checked against the engine's capture.
- The base's exact position and velocity are kept in the project; the save file rounds them
  to 4 decimals, so a load restores the exact floats (only within that rounding).
- Some cold loads of a bhop_eazy line ended 0.7225 units off from tick 277 and were reported
  "DIVERGED at tick T (max D)". This was first blamed on the engine's sub-tick carry, and that
  was wrong. Per-tick dumps showed func_bhop counting its 0.1 s on server time, so the block
  teleported a tick apart. P1085 counts ticks, and every load now reproduces exactly.
- The shared world is not rewound: moving platforms and triggers that depend on time are
  not part of a project. A `reconnect` also leaves your previous body in the world for a
  while; a line that runs into it stops there.
- The base save is a normal TAS save. Deleting it, or changing the map file, zones or
  movement rules, makes the project refuse to load rather than approximate.
- Projects stay TAS: the base is a TAS save and every load marks the attempt TAS.

## Limits

About 24 minutes of ticks per project, 48 checkpoints, 64 projects per map. Inputs come from
the attempt's recording, so a save covers everything since the base. A first save starts at
the oldest exactly-kept tick (about the last 60 s). Saving an existing name needs `force`
unless it is the project you are on; going back before the base, or rewinding outside the
TAS controls, leaves the project's line (save under a new name). Needs `rec_stream 0`.
