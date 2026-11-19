# P1623 — Linux PowerShell build/deployment support

19 November 2026, EpicOwl. Baseline game `39df032513819ef631b1689e493d91146cc90cc7`;
engine documentation baseline `4c63b07df`. Existing unrelated `ROADMAP.md` work was preserved.
No game QC, native engine/plugin, recording grammar, schema, native pin/tag or QC Build89 change.

## What is working

- Official portable **PowerShell7.7.0** installed on Lex's Linux workstation under
  `~/.local/share/powershell/7.7.0`, with `~/.local/bin/pwsh` launcher (telemetry defaults off).
  Archive SHA256 `c89d9c682d2c403dfe726f3df948e359675235a5bd6fab535776de69729ca0cb` matches the official
  checksum manifest and release API digest. No root/system package/SSH/sudo-policy modification.
- `src/build.ps1` discovers native Unix fteqcc, defaults to the sibling engine tree, has no implicit Windows
  second install, and selects the native Linux client for `-Run`. Windows compiler names/defaults remain.
  Windows-targeting `-Engine/-Full` refuse on Unix before any compilation; use the existing Linux wrapper.
- Real PowerShell **NoDeploy** compiles all three VMs with **zero warnings**, byte-identical to the current
  Linux wrapper output. Installed files were fingerprinted before/after and stayed unchanged.
- Existing PowerShell SSH transport performs an actual read-only UTF-8 stdin/stdout round-trip to the Pi.
  Remote action was Python `print` only: no files/stages, restarts or permission changes.
- Legacy `tools/surfd-deploy.ps1` retains inert `-PlanOnly`; Unix apply requires an absolute ordinary owned
  `-WorkRoot`. Every lexical ancestor/owner marker is checked, and unresolved/redirected mounts fail closed.
  Normal Btrfs subvolumes and proven identity mounts remain allowed. Remote staging quotes the complete
  parent/stage/owner-message shell arguments, including apostrophes. Existing Windows work-root default stays.

Canonical game checkout:

```sh
cd ~/Projects/WorldofSurf
wos-lock game -- pwsh -NoLogo -NoProfile -NonInteractive \
  -File ftesurf/src/build.ps1 -NoDeploy
```

For a game worktree, pass `-FteRoot ~/Projects/WorldofSurf/ftequakers`. Keep the whole dependent build/test
under one game lock; do not remove a busy lock. Native Linux builds remain `wos-build.sh engine/full`.
PowerShell is required on the host only, **not on the Pi**.

## This is not a new deployment route or authorization

The entire official Pi block's **45 statements** remain text-unchanged (the AST comparison normalizes only
line endings). Installing PowerShell does not supply its recorder/
resume/actor/archive/source-bound caller protections. Do not invoke the bare block as a shortcut.

The current sealed-backend successor consumer is already Python3.11+/Linux. It still needs a freshly reviewed
packet bound to the actual source/predecessor/readers and the existing owner-authenticated Root installation
step. The legacy helper's WorkRoot portability is **not permission to edit a sealed live generation**.
No general passwordless root, stale transaction replay or alternative deployment framework was added.

The earlier P1619–P1622 delivery's statement that a missing PowerShell/privileged environment blocked Linux
was overbroad: PowerShell is now installed; it is not needed remotely; and the Pi's per-command sudo grants
must be evaluated for the exact approved command. The read-only probe found the backend healthy and 12 lobbies,
with command-specific rules. A failed `sudo true` was not proof that all deployment operations were unavailable.
No restart was performed merely to test authorization, and listing a rule is not current Root packet approval.

**Actual delivery status:** local environment and repository portability code verified. No public lobby,
backend/catalogue, updater or release deployment. The remaining rollout work is ordinary fresh transaction/
payload qualification and owner authentication, not a missing PowerShell dependency. The retained historical
fleet caller has old host-local bindings; a fresh Linux-bound preservation transaction has not been constructed
or executed by this task. That binding/adaptation must be reviewed with the actual deployment packet, not
replayed from an old receipt. P1622's catalogue must still wait for its parser/course gate in the guarded backend generation. See `backend-pending.md` and `../lextest.md`.

## Tests, controls and review

- `tools/test_linux_deploy.py`: **7/7 pass**. Synthetic compiler actually runs; unchanged old discovery fails,
  candidate acts, NoDeploy leaves installed fixture bytes alone, compiler override/native names work,
  unsupported/conflicting flags refuse before output, and official Pi body text/count remain identical.
- Extracted real staging helper is shell-syntax checked and executed only under the owned fixture: apostrophes,
  spaces and an injected `touch` payload remain literal; ownership text/directories match and marker stays absent.
- Actual linked-parent refusal keeps a target sentinel unchanged. Extracted real mount parser checks visible and
  hidden-origin subtree aliases, escaped spaces, full-root ambiguity, malformed/missing metadata, legitimate
  Btrfs home subvolumes and identity mappings. No privileged kernel mount was created for tests.
- `tools/test_surfd_deploy.py`: **26/26 pass** after final fixes. Its real flattened-collector sub-suite passes.
  Full publication-failure test supplies the new owned WorkRoot precondition; refusal/transport/creation
  assertions remain unchanged. No network or live deployment in these offline tests.
- A rerun initially reused the collector's persistent replay/cache files and failed 24 nested assertions.
  The maintained harness now uses its already-existing per-test TemporaryDirectory and asserts freshness;
  it does not clear or relax collector state/guards. Same outer output was reused successfully, while the old
  failed cohort's **2,201 files** and complete content fingerprint remained unchanged. Failed logs remain failed.
- Independent reviewer found two P1s (shell quoting and ancestor/mount ownership); both fixed and re-reviewed.
  Final verdict: **no issues, merge OK**, not deployment approval. Real Windows and native Linux `-Run` remain
  untested; compile-byte agreement alone is not client gameplay or compiler/runtime qualification.
- Real QC output SHA256s: server `e76cb0c28c70a8b9728b51ac6c460e536964065a3b324d25d070c5460270ea66`,
  client `7d3d0dffffc7821e959a87d87516838012503ec5998c4b0c96b71caed4b24149`,
  menu `8ca956bcc81ace34cef09ddfdc21613d6125436877e0441a5a1228f5142eefc0`.

Clean implementation commit `409b01c56916a999aebd68584abb2d9a67c7a6cf` was then checked out independently:
real PowerShell NoDeploy again produced all three zero-warning VMs, identical to the measured originals;
focused7 passed again, installed hashes unchanged. Compiler identity was checked before/after from the original
measured receipt (`6eef0cb43667f93a398798ac46002b7b65ae7cc9d063e7fba3a1f6452a224173`), not inferred from
prose or current tool availability. This still is not game-runtime or live-transaction qualification.

Private source/probe/review/failed-fixture logs and dependency receipts remain in the owned task root with
OWNER.md/checkpoint. No private operational designs, credentials, player data or maps were published.
