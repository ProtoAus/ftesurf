// Patch 915: successful completed-stage write, before pruning. Definition is
// after sv_account (proven install key) and sv_share (private net transport).
void(entity e, string path, float buf) Archive_Seal;
// P1559: successful writer-owned full completion, buffered/streamed/native.
void(entity e, string path) Archive_SealFile;
void(entity e, string leaf, string map, float runleg, float ticks, string ridseq, string nonce, string profile) Archive_HistoryKept;
