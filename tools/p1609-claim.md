# Patch 1609 claim (Claude Code worldofsurf-43, 18 Nov 2026)

The angle cross-check's one-frame rule (tools/reccheck.py angle_join) stops convicting at a fallback join. When no
offset lines the .rec and .view up to 0.05 deg and P1599's sweep join names a different offset, the one-frame rule
does not judge (BLIND, with the reason), instead of faulting at offset 0. Live receipts: 84 angle FAULTs on 16
players, 81 of them this rule at the fallback (72 with a named sweep offset); on 507 lobby pairs the rule aligned on 4.
Verifier change: lens reviews, corpus sweep and fleet comparison before it rides the next surfd generation.
