# P703 — bounded native recovery retirement delivered

## Problem / fix

Reduced recovery journals lose the names needed to retire already resolved
staged objects after interruption. The native updater now retains every original
signed transaction row until conservative named-stage retirement finishes and
removes authority last. A complete, readable signed closure can retry cleanup at
attempt3 without spending content attempts; incomplete exhaustion still refuses
before mutation. Windows hashing verifies successful byte count against opened
length and close, rather than accepting zero-on-ReadFile-error as EOF. A retained
generation blocks new native apply until launcher reconciliation.

No directory sweep or adoption of arbitrary staged objects is added.

## Inspected source and publication

Engine commit **61466a48f3d76139318fbbeab77e503334746f1f**, tag **patch-703**,
pushed to engine main. The commit changes only `engine/common/qkupdate.c` and
`ENGINE_PATCHES.md`. qkupdate source SHA256:
`7321da290913f67c047f1cf86103203ad79327d05dbacb44fe7ca9da695ec5d3`.

New readlock tooling commit **4bdbeac60301f44683d190240f1e9d70fde25d1e** was
integrated without editing historical actors/graders. This record's QC commit
updates the engine pin/tag/patch, closes the completed backlog and records the
measured lifecycle lesson. QC Build/public version/feed remain unchanged.

A peer published an unrelated P702 while this task was finishing. The first
engine push was rejected without changing any remote ref. After fetching both
repos, the unpublished local entry was renamed P703 and rebased onto the peer's
**documentation-only** engine changes. No published history was rewritten and
no peer source/progs/config was deployed by this task.

## Verification

- **199 portable native-tooling tests pass**, including 11 new byte-lock oracle
  controls. `tools/test_reccheck.py`: **306 checks, zero failed**.
- Independent product-source review: no issues. Independent fresh readlock
  source/raw-export review: **merge OK**, no issues.
- New comparison uses valid protected JSON plus whitespace, **6 MiB +29 bytes**,
  all821 signed rows, attempt3 and a genuine successful shared open followed by
  ReadFile error33/zero bytes. Blocked87326b boots and incorrectly retires journal
  plus three names. Corrected7321da refuses with the entire838-file seed and
  directory namespace unchanged. After release, corrected recovery ACTS deletion
  of exactly the journal/three named objects, preserving the edit and siblings.
  Both locked probes occur before launch and after natural job0; release restores
  one-byte readability before full export. Zero signed-mirror requests is the
  bounded network claim. See `native_retirement_readlock.md`.
- Existing cold20-case/35-phase matrix passes on the integrated binary. The final
  stamp-only P703 rebuild has identical PE image base/RVA/executable text and
  unchanged engine source, with a separately passing exact-final readlock pair.
- Clean same-toolchain control and final builds succeed: each has37 compiler
  warning occurrences, identical path-normalized payload/location multiset
  (35 distinct), hence **zero NEW compiler warnings**. Each also has222 existing
  parallel-Make grouped-peer-target warnings; template/count match, not arbitrary
  nondeterministic `.d` peer names. Full tracked-source hashes are stable.
- Prior accepted fault/interruption/apply/launcher controls remain in
  `native_retirement_windows.md`, `native_retirement_interrupt.md`,
  `native_retained_apply.md`, `native_retirement_launcher.md`,
  `native_initial_superset.md`, `native_cold_superset.md` and
  `native_deferred_boundary.md`. These are separate receipts, not relabelled runs.

## Windows delivery — 2026-10-14 11:58:21–11:58:24 UTC

Exact clean-build executable SHA256:
`51e1109faea5d0fee6aa96720d9dbabc5628650e93ffa928479f2b7e7d8ece4c`.
Matching companion SHA256:
`566afaa329b7b4504ee1110e68f16bf1da0dda4e7833b510df21871d231b1799`.

Identical executable delivered and read back at:
- `C:/FTESurf/ftesurf64.exe`
- `C:/FTEQuake/fteqw64.exe`

Both retain exact preceding bytes in `.prev`, unique
`.pre703-20261014T1158Z` predecessors, and immutable owned-root backups. Existing
`.prev` bytes were backed up too. Server, plugins, progs, default/owner configs
were guarded unchanged **during the swap**. Only the two client executables were
deployed: no header, plugin/server ABI, QC build, Linux/Pi/fleet or public-release
change. A later recheck found external changes to both installs' csprogs.dat and
the primary owner ftesurf.cfg; actor attribution is unknown. They were not
repaired/reverted, and no globally frozen canonical-state claim is made. Both
P703 client hashes and predecessor/.prev bytes remained exact. See owned-root
artifacts/post-delivery-peer-drift.json.

Both **installed executable paths** pass shared-open/read-failure refusal and
released ACT cleanup in separate owned synthetic basedirs. Canonical installs
have five adjacent plugin DLLs; existing `PM_PreparePackageList` inventories them
before recovery (`client/m_download.c:2135–2169,2199–2262`). Delivery fixtures
therefore independently author the deterministic five-plugin `installed.lst`
BEFORE either phase and require its exact bytes to survive the unchanged complete
namespace grader. No grader allowance, monkeypatch or canonical installed.lst edit.
This source-proven setup difference is not a new recovery exemption.

**The owner's running game was not stopped or restarted.** Its old mapped image
continues until the owner restarts normally; new launches use P703. Installed-path
acceptance processes were our own suspended Windows jobs and naturally reaped.

## Evidence and failures retained

Owned root `C:/FTESurf-worktrees/wjship-20261014T114200Z` contains OWNER.md,
artifacts/build-{control-02,subject-03}.{json,log}, final-stamp-binding.json,
final-core, final-readlock03, readgate, reviews, windows-deployment.json,
installed-{primary,secondary}-catalogue and exact runner scripts. Runtime and
full exports are retained for review; historical task roots were read-only.

Initial parent build setup FAIL (wrong path separators/PATH), naive warning
comparison, two binding-script import/type mistakes, rejected racing P702 push,
and installed-path build-output-path assertion remain distinct failures. First
primary native delivery fixture also remains FAIL/guard/runtime: missing baseline
plugin catalogue added `installed.lst`. Raw export/job0 prove the cause; only the
fresh independently authored delivery fixture passes. No failed run was relabelled
or blanket-cleaned. The historical provider-failed lane is untouched.

## Explicit limits

This completes the bounded Windows native retirement work, not every proposed
updater experiment. No power-loss/directory-flush certificate, hostile concurrent
ancestor/hardlink defense, broad orphan collection, arbitrary byte-lock offset,
Linux behavior or all-network-silence claim. Failing cold product API return/path,
new attempt3-publication cuts and optional complete-content cleanup-only-at3
variants are not newly observed. Public release0.1.25 remains the existing P687
archive; no release/version/feed or QC Build bump was requested or performed.
