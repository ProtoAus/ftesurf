# P1077: retained-input timeline and bounded revisions

## Use

On an updated local server with the P1074 native engine:

1. Start recording normally, walk out of the start zone, then `tas pause`.
2. `tas timeline` opens the workshop's **Timeline** tab (`tas menu` has the same
   tab). Refresh shows up to eight retained ticks; **< 8**, **8 >** and **Latest**
   browse the last 128 ticks. A missing tick says unavailable, never zero input.
3. Click a row. **Single** selects just that tick; **From here** and **To here**
   set an inclusive range. Click the field name to cycle forward/side/up,
   pitch/yaw and jump/duck/walk; change its value or held/released state.
4. **Recalculate** changes only that field in the range, then replays the whole
   suffix to the old head. Refresh after completion to inspect the result.
5. **Undo** and **Redo** restore whole effective input tails through the same
   exact warm replay, including nonuniform inputs and unedited fields. There
   are at most eight edits. A fresh edit after undo discards its redo branch.

`tas undo` / `tas redo` also work from the console. `tas timeline status` prints
exact table words; `select tick`, `single/from/to`, `field name value`, `apply`,
`undo/redo` and `refresh/latest` expose the same table actions without a mouse.
Console `tas edit` edits also enter the revision stack. This is not route search.

## Safety and limits

- The table belongs to the player's own body, one local seat. GUI edits identify
  the displayed recorder serial, logical head and TAS request, so a stale table
  cannot silently edit a newer line. Duplicate GUI clicks are disabled locally
  and rejected authoritatively after the first request changes the attachment.
- Existing capability, duration-input, threaded-physics, streaming, recorder and
  retained-prefix guards still apply. Undo is not a bypass. Replay interruption,
  another step/back/replay, a new run or lost warm prefix can detach history.
  Unavailable exact history refuses rather than guessing. Wait for completion;
  "armed" is not "completed". Existing Play/Off escape controls still cancel.
- Only bounded in-memory effective inputs are saved in revisions, not trusted
  receipts, portable native handles or shared-world state. The world keeps
  running; dynamic triggers/movers are not a deterministic world-rewind claim.
- These are **not saved projects**. Persisted/cold-restorable checkpoints,
  immutable project chunks/contributor logs, comparison overlays and route
  optimization remain separate items in [the TAS plan](plan-tas.md).
- No native API/pin/tag, record format, QC Build, public backend or lobby native
  enablement is changed by this QC patch. TAS ancestry/practice status is retained.

## Qualification

Source implementation and initial production-socket acting controls are present.
Final frozen-source reviews, full socket qualification, isolated committed build,
dual-Windows installation hashes and owner rendered/feel acceptance are pending.
Do not infer those states from the existence of this document.
