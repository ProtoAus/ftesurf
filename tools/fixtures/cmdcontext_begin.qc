// Test-only: insert immediately BEFORE server/sv_player.qc, after system defs.
// Do not rename fixed-offset system defs with command-line -D macros.
#define PlayerPreThink P675_OriginalPreThink
#define StartFrame P675_OriginalStartFrame
