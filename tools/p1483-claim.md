# P1483 claim: Jargon search -- reproducible searches, a benchmark, beam over boards, per-map memory (ftesurf-16, 11 Nov)

Lex (11 Nov): the path search is sometimes suboptimal -- optimise it, let it learn, drop old fixes that hurt.
Plan: a seeded search RNG (the same state searches the same way; tries vary by seed); a course benchmark
(several runs a course: finish rate, time against the guide, minutes); switches for the old backtrack rules so
each is measured on and off; a course's own end teleport scored as its reach; the top candidates of a board
kept and judged on the stretch after (generalising `spots`); each map's best lines saved and used to start the
next run. On P1478 (main 45d28963).
