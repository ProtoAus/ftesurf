# P1495 — remember the selected knife across maps

## Scope and authority

QC base `02e58218d874707af1321bb8fdb18cc4f32be31c`; inspected native base
`c0e6fa2793cd3344a295dffec2354a3341e79c4f`. These are isolated candidate
provenance, not final delivery hashes. Parent integrated the accepted source,
claimed1495 after both-repo fetch/max1494 and owns commits/promotion.

The 21-field linked-account setup already contains knife, finish, hands, sleeve,
visibility and their presentation parameters. It does not contain equipped weapon.
`PutClientInServer` explicitly starts unarmed each map, and the old Drop paths
only sent `weapon_drop`. `cl_viewweapon` is visibility, not equip intent: it stays
separate. The existing server weapon-selection command remains authoritative.

Add local archived `cl_knife_equipped`: -1 is unset, 0 is explicit Drop, 1 is
remembered equip. An accepted, actually applied, saved enabled account setup
migrates -1 to 1; initialized local defaults and an account with no saved row do
not. A delayed account reply cannot undo Drop. The ACK is queued before restore
is armed, so the ordered weapon command cannot precede restoration of cosmetics.
An explicit knife/workshop selection re-enables remembered equip. Both ordinary
Drop and workshop Drop clear it without changing the selected combo.

The restore pump requires the existing *vmsetup capability, waits for own live
stats and positive health, retries at one second until server weapon selection is
visible, and then disarms. Any selected gun also stops the pump rather than being
replaced. A map-local explicit-choice latch prevents a later account reply from
rearming after an explicit gun request, even before its server stat arrives.
Deferred catalog choices carry a local integer epoch: Drop/new choices invalidate
older completions before they may apply cosmetics, re-enable intent or request a
knife. Automatic content mounting requests readiness only, not a new selection.
The pump does not force visibility or change one-shot explicit weapon commands.

Cold automatic mounts mark a missing-model presentation failure. A readiness
callback may reopen that cache only if the same current knife is still failed,
its actual model file now exists, and the local player has not explicitly Dropped.
Already-ready presentations, newer guns and changed model identities are untouched.
Success clears only the failed model-name cache/marker; ordinary WP_Frame then
loads it. Still-missing content leaves the failure latched, so ordinary frames
cannot repeat mount/file work. No cosmetics, intent, choice epochs or weapon
requests are changed by the readiness helper.
Equip opt-out is local per install; the existing combo remains cloud-linked.
Automatic restoration is armed by the supported account load/none handshake,
not an unlinked/offline startup with no account response. Explicit selection still
works immediately there. No account protocol/storage migration is introduced.

## Predeclared acting controls and results

`tools/test_knife_equip.py` declares and runs source-bound scalar helper controls:
no saved combo cannot migrate; late account response cannot equip defaults;
saved enabled combo migrates; non-own stats/dead body cannot send; own live body
sends; missing selection retries only after cadence; real server weapon stat
stops; next map rearms only on readiness; Drop survives later loads/maps;
explicit next selection enables; gun authority is preserved. The localcmd stub
counts actual knife/drop requests and rejects every other command; the cvar
stub accepts only equip intent, so cosmetics/visibility writes fail the test.
Seventeen source-wiring assertions bind accepted-row/ACK ordering, pump/UI paths,
explicit cancellation, epoch-bearing queues/completion and readiness-only mounts.
Additional deterministic controls cover explicit gun request with stat still zero
followed by account-ready/pump, queued choice then Drop then stale completion,
a genuinely later re-equip, stale choice after gun/new catalog choice, and absent
capability. Three guard-disabled negative controls must each fail their matching
assertion; all three do. A fourth guard-disabled control removes failed-cache
invalidation and must fail the cold ordinary-retry assertion. Cold/still-missing
controls count probes, mounts and loads over twenty ordinary frames, then verify
one successful retry and no repeated work. Ready-gun, Drop and changed-model
controls reject unrelated callbacks. The production helper and WP_Frame cache
comparator execute with counted asset/load seams; the full WP_Frame does not.
The model-validation seam is stubbed successful for the completion test, so a
stale completion must fail before entering that seam.
These helper bodies execute as C with builtin seams stubbed. This is NOT an
actual QC VM, socket/account round-trip, rendering or performance pass.

Command (from candidate QC root):

```
python tools/test_knife_equip.py --work-root C:/FTESurf-worktrees/playerfix-20261110-01a1c798/knife/tests/cold-retry
```

Passed; strict gcc -Wall -Wextra -Werror, no diagnostics in all five variants.
Initial cold-control harness compilation rejected misleading indentation; corrected
with braces and retained as subject-compile-initial.log. Product build stayed clean.
Subject passes, while individually disabling account cancellation, completion
epoch rejection or capability gating produces its expected assertion failure.
Logs and generated exact helper sources are retained in that owned directory.
Earlier evidence remains under tests/equip and tests/equip-review. The former
missed the pending explicit-gun/stale-completion windows; the latter missed cold
model retry. They are retained historical evidence, not current acceptance.

Standard build (from src, PowerShell 7):

```
pwsh -NoProfile -Command './build.ps1 -Jobs 8 -NoDeploy'
```

Qualified compiler SHA256:
`73f9a1a471d603a8d0ee5a83432229ba2dd10affbf358ba41d345c8c15af68c4`.
It was copied read-only from `C:/FTESurf-worktrees/compilers/fteqcc64-p1412-73f9a1a4.exe`
to the owned src compiler location. Both pristine base and final subject compile
all THREE VMs with zero warnings. Initial candidate compile failed on missing
forward declarations; fixed by following the existing WP_LocalZoom declaration
seam before cl_weapon.qc. Preserve the initial failure log, not a pass claim.

Retained build outputs under `knife/qc/rig/`:

- Current cold-retry subject: `build-nodeploy-828ba9f44f304f78995045f30f37143b`.
- Previous guard-only subject (superseded): `build-nodeploy-ad08db30224d41e0acd087e19422b18d`.
- Pre-review subject (superseded): `build-nodeploy-748a887bea3f4425a0924bfc885514c9`.
- Pristine base control: `build-nodeploy-dce0367ddaa84463ba4191675a529e5b`.

Isolated candidate hashes (not the combined parent artifact):

- csprogs.dat: `9054e4c96fa083b56d63e105a65bc8117c705a8d6958fe7b351a7a855dffc599`
- qwprogs.dat: `fdce20d0ea73bad787fbdea4d3518de85adbc79110cd5120ce088eed23b88bb7`
- menu.dat: `0bbd8c3739eed3f99d11a21fcb6a3c4cd435c61b703787e436d2cd277e5d19f5`

Base source was obtained with git show into the three owned files for the control
build and restored byte-for-byte in finally; no canonical/peer file was changed.
`git diff --check` passes. Corrected subject server/menu hashes match the retained
pristine control byte-for-byte; only CSQC differs. The corrected standard THREE-VM
build has zero warnings, logged in knife/artifacts-build-cold-retry.log. The full
tracked client-source diff is retained as knife/equip-review-source.diff; the two
new tools files must accompany it. knife/cold-retry-source.diff isolates this
follow-up against the previous guard-corrected candidate. Final independent
re-review found no issues after the ordering/capability/cold-cache repairs.
Parent combined build-nodeploy-ca21c5f85d3c4eed8165d459c198189d compiled all
three production VMs with zero warnings. No live/rendering pass is implied.

## Rendering trace and concrete remaining blocker

No renderer, GLSL or lighting change is included. The owner-reported black skin
after a map change is NOT reproduced or proven fixed by this patch. No GPU/game
was launched; parent withheld a render interval because peer benchmark actors
occupy it. Need exact affected combo and either small owner observation or a
coordinated quiet render interval before a supported material fix can be made.

Source facts, not fresh live verification:

- P957/P962 establish installed catalog/material preview handling; P970 already
  transports cloud combo, and P978 protects explicit Reload versus local edits.
- P1280 already shares rate-limited viewmodel lighting across knife/hands/sleeve;
  `Surf_NewMap` advances the model-light sequence, and the cache also rejects time
  rollback/large movement. Viewmodel minimum ambient light already exists.
- `Shader_Reset` preserves dynamic generator/script arguments across reload.
  `Shader_TouchTextures` touches used shader images before image purge. A guessed
  per-frame shader/texture/lightmap rebuild would not establish the black root.
- Original lit replacements use defaultskin; painted previews use knife_finish.
  Thus do not claim a newly unified appearance pipeline or all-catalog consistency.

Small owner probe, no new automation: use the exact affected saved combo in one
lobby; run `weapon_info` and `knife_menu status`, take a settled ordinary-view
image, change map normally, run the same two queries and take the black image.
Then `knife_menu select <same catalog ID>`, wait through draw and capture again.
Report whether blade, hands, sleeve or all parts are black; whether Original
versus the affected finish differs; and whether same-ID reselection recovers.
Avoid flushshaders/reload/mount changes before the comparison. An owned GPU
interval, if later granted, needs only one client on owned dedicated port27603
(after free-port check), two map loads and these same fixed captures; no shared
fixtures or competing benchmark actors.

Parent may independently review/integrate the equip portion while blackness and
visual/performance acceptance remain explicitly pending. No Build bump, patch
reservation, commit, staged files, installed changes or public release here.
