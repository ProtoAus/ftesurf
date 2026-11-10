# P1478 claim: Jargon courses -- one click for main, bonus or stage, and Continue (ftesurf-16, 11 Nov)

Lex (11 Nov): start maps, bonuses and stages with one click, or continue where you left off; searches that look
for the correct thing. Plan: the panel lists the map's courses from its zones; guide runs are filtered by their
.rec header (track, leg) so a bonus replay is never offered for the main start; the server picks the start zone
from the guide and, for a stage from a full-run guide, starts the plan at the guide's own crossing; each reached
stretch autosaves a legal-start TAS project plus the chain's records, and Continue loads it and goes on. On
p1449-wall (15de0242).
