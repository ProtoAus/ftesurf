# P726 — chat spectate aliases

## Behavior

- `!spec`: spectate the next eligible player; while watching, leave through the
  existing return countdown.
- `!spec proto`: select a player by case-insensitive exact name or unique prefix.
  Existing matching strips colours and accepts multiword names without quotes.
  Ambiguous, unknown and self names retain the existing explanatory refusal.
- `!spec off`, `!spec next`, etc. are the corresponding existing console actions.
- Whole-message `say`, split-token `cmd say` (the chat draft) and `say_team` work.
  Handled aliases are not broadcast; other chat still is.

The server's existing chat parser sends one `%S`-quoted trimmed argument to the
existing client `spectate` command. No new camera/hold/movement/recorder logic,
native engine change, engine pin/tag change or QC Build-number change.

## Falsifiers

Inspected clean bases: product `37e2298ac8dcb84487c4f8d01ea0e8899f5c3856`,
engine patch documentation `85ef3e3f2f6a9f8adaada1117225ceb2a82f2d40`.
The P724 delivery receipt's three VM hashes exactly match the pre-change control;
no older canonical dirty source or uncommitted peer work was built or deployed.

All three VMs compile with **zero warnings**, both before and after. Command:
`pwsh -NoProfile -Command './build.ps1 -Jobs 8 -NoDeploy'` from `src/`.
The final original-manifest build (`./build.ps1 -Jobs 8`, same clean owned tree)
was independently exercised before publication/deployment.

```powershell
python -B tools/spec_chat_smoke.py --progs <pre-change-output> --out <owned-root>/control3 --control --port 27615
python -B tools/spec_chat_smoke.py --progs ftesurf --out <owned-root>/final-subject --port 27615
```

The driver owns one real dedicated socket and three client processes, each with
an isolated gamedir/config/data root. Pre-change **6 checks pass**: both aliases
actually appear in chat and do not spectate, while console entry and countdown
exit ACT. Final subject **25 checks pass**: entry/toggle/negative countdown/body
return; coloured/case-insensitive multiword exact name; split chat-draft sender;
team chat; unique prefix; ambiguous/missing/self refusal without changing the
current target; semicolon tail cannot issue an additional command; ordinary and
other-exclamation chat; no alias broadcast; no-target uppercase alias with no
pending camera request. All four logs have no command/VM errors and all owned
process handles are reaped. Server dispatch and client status replies are graded,
not inferred from quiet logs. No visual camera-quality/input-taste claim.

Failed harness iterations are retained, not counted as product passes: initial
viewpos expected integer coordinates rather than the actual decimal response;
next chat matcher omitted colour-reset tokens and lobby mode was not enabled;
first subject's server cfg sent client-only `cl_idlefps` without `set`; no-target
arm expected a console message that is actually only a HUD flash. Corrected
fresh arms passed. No production logic was changed in response to those errors.
The fixture's minimal raw map has no useful floor: positions can fall, which does
not affect this command-routing/camera-state test; this is not movement evidence.

Final verified VM SHA256:

| File | SHA256 |
|---|---|
| qwprogs.dat | `7fb25d136e061357e68d0543dd9f9593e0370c0a563a9b494913704ac26729e2` |
| csprogs.dat | `a78f8dd66f92ff5f3caa1655c2e05107f53237f67300e9baaf030d8584213ce2` |
| menu.dat | `44f12fd918278bd160db66f6cfb45b176d56eeb6290e3d28e6365e81e3bbcbd9` |

The original product commit `87f4870` used P725. A concurrent portal engine
commit claimed that number between our fetch and push; its native changes were
not incorporated into this QC-only build. This feature is renumbered to P726
without changing code or tested bytes. Portal P725 remains its author's separate
paired native/QC delivery. No published history was rewritten.

## Delivery — 2026-10-15 UTC

Product code `87f4870ce61f2a0d459828ac14bbf6ec8ef5bbe8`, renumber metadata
`c9b6416adcf5b6cf8cc40cc61125a4fd22cb1c3c`; final engine patch documentation
`a528fb76e07647504789b2cdc436ec08e23f1d99`. Exact inspected SHAs pushed to
main. The native engine/pin/tag did not move for this feature. The engine-doc
commit is atop the peer's published portal commit, but NONE of its native or
unpublished paired QC was built/deployed by this task.

The clean inspected QC tree ran `./build.ps1 -Jobs 8 -Pi` (pwsh7): all3 VMs
zero warnings, all12 positive directory rows at0 players, uploaded pair verified
before swapping, ordinary `.prev` backups kept, all12 services restarted. The
VM hashes above exactly match the original-manifest subject, not just equivalent
source. A readback at10:10:32Z showed both expected live hashes and all12 active
services. At10:13:55Z the hashes remained exact and EVERY process PID differed
from the pre-deployment receipt. No configs, native binaries, backend or release
assets were copied.

Both Windows gamedirs were independently verified at10:12:24Z: all3 VMs match
the table, and protected owner cfg hashes were unchanged. Only qwprogs changed;
rollback copies in each install are `qwprogs.dat.pre-p726-20261015T101224Z`.
The unchanged CSQC/menu files were not needlessly replaced. The Pi retains its
previous pair in `.prev`.

A fresh two-client join to live lobby1 (surf_kitsune) fetched the EXACT served
CSQC hash for BOTH clients, with no pre-seeded cache. `!spec spec726proto`
selected our second owned test player; live status showed the actual target and
the inspected screenshot showed `WATCHING Spec726Proto first person`. Bare
`!spec` produced negative countdown stats, then stat0/body return; another bare
entry and explicit `!spec off` also acted. Seven live assertions pass; no
command/VM errors and both owned client handles reaped. This is live command/
state/UI proof, not a new full-map camera-quality or movement/evidence test.

Local evidence/source recovery was retained under the task OWNER.md root;
verified disposable worktrees and runtime copies were retired after publication.
No owner game process or another session's source was stopped/reverted. The
original engine-doc push was safely refused on a concurrent non-fast-forward;
P726 documentation was reapplied atop that inspected published parent, without
force-push or rewriting history.
