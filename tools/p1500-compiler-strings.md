# P1500 — compiler string append bounds

## Change and limits

A compatibility-dialect string append now uses the existing token capacity and
length-error path before writing, reserving the final terminator. Accepted
strings and their complete embedded-NUL byte payloads retain existing semantics.
This is narrow compiler defensive hardening, not an anti-cheat detector,
sandbox, measured exploit or remote-reachability claim. No input capture,
evidence grammar, scoring, enforcement, mover, settings or QC Build change.

## Qualification

- The real standalone compiler passes six successful full-string payload checks
  and three acting length-refusal controls. Checking the emitted string section
  proves the append and complete NUL-preserving result actually occurred.
- An actual compiler built with the proposed guard omitted safely intercepts the
  two old out-of-bounds append attempts before writing. The untreated unsafe old
  compiler was never executed. A one-byte-too-strict compiler rejects the two
  legitimate separator-capacity controls, which the subject preserves.
- Independent frozen source review is CLEAR for the two-line production repair.
  This is not parser-wide audit completion or live remote-dispatch acceptance.
- Supported standalone compiler and full Windows client/server/five-default-plugin
  builds pass. The full build's 74 native warning payloads exactly match the
  prior qualified baseline: zero new. All three production QC VMs compile with
  zero warnings. Known Q208 system-header warnings in deliberately minimal
  compiler fixtures are recorded separately, not called product build warnings.
- Initial private environment/fixture mistakes are retained, not regraded.
  Optional dialect/escape fixtures with invalid test inputs were excluded from
  acceptance; the original nine required capacity/payload/refusal cases remain.

## Publication and delivery

Published engine source: `b077b6715ac9bcefecac13949075b3b3c5c5a086`,
tag `patch-1500`.

Final clean full rebuild and guarded dual-Windows delivery are **verified**.
At `2026-11-11T08:17:31Z`, the seven qualified native images in each install and
the existing developer compiler were promoted through the source-pinned build
entrypoint's existing `Deploy` function. All 15 destination hashes and immediate
predecessors in `.prev` were verified, with separate rollback copies retained.
All 12 protected VM/config identities remain unchanged; no process was killed.
Both actual installed clients report `git-8684-patch-1500-0-gb077b6715`.
The installed developer compiler passes all nine required controls. Its stock
make metadata uses annotated tags, yielding clean
`git-8684-patch-1498-2-gb077b6715`: the exact same published source SHA.
The published lightweight `patch-1500` tag is unchanged; no history/tag rewrite.
All 5,882 shared read-only dependency members and bytes match the prior baseline.

| Artifact | SHA256 (same native image in both installs) |
|---|---|
| client | `ba2d0c2a6e8d113e79fb924dfd7b135ccd51898e3b4269722dc0467a1247a728` |
| server | `811340d967737831fc0d98c303130a517ef4a73edb20c409650a15c413ffb9b1` |
| hl2 plugin | `4bea0d59593b4a73ef3ba47e36ffb1c9b42006e34a623c439690ff9c2b861b1e` |
| cod plugin | `0006571b3b1926d043985df9d0540c6dd69fbbc0fa5afbe95845baf136a99d38` |
| box3d plugin | `933a59349e5e56cfae780423745d399a6c89de274f49c78ac69df5ef07ad2494` |
| ode plugin | `86bb6ebc7cfdc761db1690d630a722eca968e5bd2bbba6e164ecd667ac1f6917` |
| ui_imgui plugin | `904663449d3b53a2ff4cf83979a28e622dac057288f083c23c76eb0aa9ebb9bc` |
| developer compiler | `b47411935afe25fc457f681466666acf12b18b7f3c225a37d4e5ed71f751ecfb` |

An initial incremental compiler retained an old version constant; it was refused
before deployment. A forced standalone build restored clean source identity,
without repeating the already-qualified full native build or changing source.
A dedicated-server `--version` probe did not exit and its own timed-out child was
stopped; no server runtime acceptance is inferred from that probe. The client
version checks and actual compiler controls above did complete.
No backend generation or lobby progs swap occurred. This is a development native
and compiler delivery, not a release or completion of the broader security plan.
