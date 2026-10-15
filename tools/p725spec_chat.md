# P725 — chat spectate aliases

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

Delivery/UTC provenance follows after destination and live acting checks.
