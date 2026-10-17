# P763 — the Kitsune stutter: the tempstring GC skips the run-line pool

The owner (17 Oct): "the fps in the map does seem poor, it seems to stutter periodically, like
the 1% lows are bad". P758's diagnosis (`tools/p758portalsky.md`) found the cause: the CSQC
tempstring collector copies or scans the whole QC hunk every ~415 frames, and Line_Alloc's
~80 MB of float/vector arrays is in it from the first line.

## Change

- Engine 763 adds the CSQC builtin `memnostrings(ptr)`. The GC's two read paths leave a marked
  block out, and `memfree`/`memrealloc` forget it. ENGINE_PATCHES.md Patch 763 has the rules.
- `cl_lines.qc` Line_Alloc marks its 29 float/vector arrays when `checkbuiltin(memnostrings)`.
  Older engines skip the call and keep the old cost.

## Falsifiers

- `tools/test_qcgc_nostrings.py --engine <ftequakers> --out <owned dir>` runs the real initlib.c
  code. In 40 random sequences of alloc, mark, free, realloc and forged headers, the marks of
  both read paths equal an oracle scan (~30,000 checks). The model restates the registration
  rules, so the harness checks bookkeeping and reads, not the rules themselves.
- Four controls fail `marks_ok`: no drop in memfree; a drop only of registrations that start
  in the freed block (review round 1); skips not cut to whole words; unsorted insertion.

## Native arm `p763gc`

Run on the owner's PC: surf_kitsune, 2560x1600, `cl_maxfps 0`, renderscale 2, recursion 2.
It walks the hub, crosses the door, walks back for 2 x 3 s, then stands for 10 s.
`pr_gc_threaded` is set at launch and echoed. After each window it prints `cl_status`, and
the log is grepped for invalid temp strings and run errors. Engine `ea705b69`
(`git-7369-patch-763-0-g36ab6bff5`), csprogs `260e66bf`.

| After the crossing | GC reads | ~20 ms spikes | 1% low (along2 / along3 / stand) |
| --- | --- | --- | --- |
| 763 + 763 QC, threaded | 7.2 of 86.8 MiB, 29 blocks marked | none; a 3.5-4.9 ms frame per collection | 301 / 284 / 267 |
| 763 + 763 QC, same thread | 7.2 of 86.8 MiB | none | 219 / 208 / 163 |
| 763 + P758 QC (control) | 86.8 of 86.8 MiB | 19-28 ms every ~0.5 s | 74 / 73 / 104 |
| P758 + 763 QC (compat) | no line (old engine) | 17-32 ms; no QC error | 115 / 98 / 69 |

The base fps moved between runs: along1 ran 940, 591, 668 and 615 fps. Other sessions' work
shared the PC, so compare spikes, not averages. No run printed a suspect line. A screenshot
after the stand shows the HUD's per-frame strings intact.

Still open: the average fps falls the longer a run lasts, with or without the collector
(BACKLOG).
