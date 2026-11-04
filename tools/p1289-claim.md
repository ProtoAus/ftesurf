# P1289 claim

ftesurf-ac, 20261104, Lex (4 Nov: "continue with ... the known gaps"): P1279's review residuals, client QC.
A save made in a replay marks the replay's moment (Seq_MarkView), not your live state; a restored anchor's zone
index is re-checked against the zone table (zone download/publish mid-replay); a dropped restore leaves a fresh body;
a backward seek in a replay re-anchors to its leg's start zone. Files: src/client/cl_board.qc, cl_hud.qc, cl_watch.qc,
cl_rewind.qc. Also P1280's: r_modellight_seq hashes the plugin's hl2_lt_* cvars (engine gl_rlight.c).
State: in progress.
