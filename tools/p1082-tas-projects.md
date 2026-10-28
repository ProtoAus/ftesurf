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
- The engine carries a sub-tick millisecond remainder between ticks that neither a save nor
  QC can set, and a replay keeps whatever the connection had. Measured on bhop_eazy with a
  duck-then-jump line: 3 of 5 cold loads ended 0.7225 units off from tick 277 of 281, the
  rest exact; a line without the duck reproduced on every load. The load reports this as
  "DIVERGED at tick T (max D)" rather than hiding it; fixing it needs an engine op.
- The shared world is not rewound: moving platforms and triggers that depend on time are
  not part of a project. A `reconnect` also leaves your previous body in the world for a
  while; a line that runs into it stops there.
- The shared world is not rewound: moving platforms and triggers that depend on time are
  not part of a project.
- The base save is a normal TAS save. Deleting it, or changing the map file, zones or
  movement rules, makes the project refuse to load rather than approximate.
- Projects stay TAS: the base is a TAS save and every load marks the attempt TAS.

## Limits

About 24 minutes of ticks per project and 48 checkpoints. Exact history is kept for the
last 4000 ticks; ticks older than that are copied into the project as you go, and a save
refuses (naming the tick) if any tick since the last save was not retained.
