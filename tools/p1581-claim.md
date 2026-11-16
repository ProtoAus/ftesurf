# Patch 1581 claim (ftesurf-31, 16 Nov 2026)

Content skew vs tampering: the lobby records the prop models it failed to load (`.rec` header `propmiss`), and the
verifier and reccheck name them beside a world/physents mismatch, so a lobby that missed newly installed content is
told apart from a doctored run. Root C:\FTESurf-worktrees\acguard-20261116-c5.
