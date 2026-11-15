// Patch 915: successful completed-stage write, before pruning. Definition is
// after sv_account (proven install key) and sv_share (private net transport).
void(entity e, string path, float buf) Archive_Seal;
// P1559: successful writer-owned full completion, buffered/streamed/native.
void(entity e, string path) Archive_SealFile;
void(entity e, string leaf, string map, float runleg, float ticks, string ridseq, string nonce, string profile) Archive_HistoryKept;
// P1568: implemented after the legacy transport; shared callbacks remain stable.
float(entity e, string path) Archive_StreamSealLarge;
float(entity e, string path) Archive_StreamRow;
void(entity e) Archive_StreamReset;
float(entity e) Archive_StreamBusy;
float(entity e, float argc) Archive_StreamCommand;
void() Archive_StreamFrame;
