# Patch 1613 claim (Claude Code worldofsurf-58, 19 Nov 2026)

The recorder writes each move's usercmd number (input_cmd_sequence, which the engine already publishes per command,
Patch 675) as a sparse `cseq <n>` record before an `in` row whose number is not the previous row's plus one (the
run's first command, and after each command the server never ran). An unknown record is skipped by every reader
today, so no format bump. tools/reccheck.py then joins each move to the .view frames of exactly its own command
(`cmdframe`) and applies P1610's drawn-path test with no inferred offset. Recorder + verifier change: lens reviews,
corpus and fleet checks, the reader first in a surfd generation where it convicts, then lobby QC.

19 Nov: built and reviewed (three rounds; branch p1613-cseq, 84dd6747 -> 6dba844e -> 541165ed). Not deployed: waits
on a real client's .view beside a `cseq` recording, then the recorder on the lobbies, then the reader (BACKLOG).
