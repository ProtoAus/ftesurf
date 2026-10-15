# P721 cache settings readback reader

Pure, in-memory Python tooling: historical settings diagnosis and a stricter
**proposal**, not a command-line application or an integrated capture gate.
Imports only `decimal` and `re`; no project/native imports, file I/O, subprocesses,
sockets or native operations. Callers supply an already bounded reply, not a
cumulative console log. This is not an instruction to run a native capture.

## API and checks

- `audit_preserved_settings(text, cache=0)` checks 36 real settings, including
  cache phase, plus exactly six historical Unknown replies. It diagnoses the
  historical instrumentation mismatch; it cannot certify no-overlay state.
- `proposed_settings(text, cache)` additionally requires 13 real HUD controls
  disabled: 49 value observations, plus the same six Unknown replies. This is a
  settings-only candidate, **not no-overlay or native/original-packet approval**.
- `parse_readback(text, required, expected_absent)` requires explicit nonempty,
  disjoint memberships and returns observed effective strings. All violations
  raise `ContractError` (`ValueError`), including under Python `-O`.

Each name must occur exactly once. The six historical names are `hud_timers`,
`hud_pb`, `hud_spectators`, `hud_statusbar`, `hud_lobby`, `hud_surfinfo`: each
requires one exact Unknown reply, not a value even if zero. This is not a prefix
allowance, a general future exemption, or permission to invent cvars with `set`.
Missing values are never synthesized. Real controls cannot be Unknown.

The immediate Effective line takes precedence over the first requested/latched
string; Default is informational, not an effective value. Duplicate/orphan
records, unsupported pending video/map/renderer latch output, unexpected output,
wrong renderer (`gl` required), wrong mode (`r_blendsort=1`) or invalid cache phase
(integer 0/1 only) fail closed. Fixed numeric strings use the ASCII subset
`[0-9]+(?:\.[0-9]+)?` before finite Decimal equality: ordinary leading zeroes and
fractions work; plus signs, exponents, underscores, surrounding whitespace,
non-ASCII digits and nonfinite values do not.

## Synthetic regression tests

From the repository root:

```text
python -B -m unittest discover -s tools -p test_p721cache_readback.py -v
python -B -O -m unittest discover -s tools -p test_p721cache_readback.py -v
```

All transcripts are explicitly **synthetic** and built in memory; no preserved
native log or witness is a public golden. Tests remove whole records (including
Default) and demand the exact named membership error for each of 36 base and 13
additional controls. Separate controls exercise malformed/orphan records,
nonzero real settings, exact six-name membership, effective/default precedence,
ASCII compatibility, numeric divergence, renderer/mode/cache and `-O` behavior.
Even the complete synthetic 49-value positive proves settings parsing only.

## Bounded source citations

These citations describe held source, not proven source-to-subject-progs lineage.
QC revision: `f277fb725bc58120f8055d8f002ed99449b775ed` (QC f277).
Engine revision: P721 `b548053218a00aa6e549dfee9ad02a65833317b8` (held engine source).
Paths below are repository
relative within the respective QC or engine repository; line ranges refer to
those revisions, not necessarily current main.

Engine:

- `engine/common/cvar.c:1513-1576`, `Cvar_Command`: first string, Effective and
  Default output; unsupported pending-change forms exist and are rejected.
- `engine/common/cmd.c:3488-3531`: cvar lookup and QC/menu dispatch precede final
  Unknown output. Unknown reports unhandled at that time, not harmless/off.
- `engine/common/pr_bgcmd.c:2007-2045`, `PF_registercvar`: existing variables stay
  intact; new registrations are user-created. `engine/client/pr_csqc.c:6946`
  exposes registercvar #93. QC `src/defs/cl_defs.qc:971,1031-1068` documents the
  cvar/registercvar interface. Missing numeric lookup returning zero is not proof
  of a disabled registered control.
- `engine/common/cvar.c:1014-1023` derives numeric `.value` / `.ival` through
  `Q_atof` / `Q_atoi`; `engine/common/common.c:620-675,679-754` defines those
  readers. In particular `Q_atoi("+1")` yields 0 and `Q_atof("1e2")` yields 1,
  unlike Decimal equality to 1 and 100. `engine/gl/gl_backend.c:7325-7328`
  requires `r_blendsort.ival == 1`; the ASCII restriction preserves that check.

QC real HUD controls (registration; relevant read/draw guard):

| Controls | QC source beneath `src/` |
|---|---|
| `hud_timer` | `client/cl_timer.qc:321,1357-1360` (`Timer_Draw`; PB belongs to this UI) |
| `hud_mapinfo` | `client/cl_hud.qc:976,756,5982-5983` |
| `hud_mouse` | `client/cl_mouse.qc:48,335` (`MPad_Draw`) |
| `hud_board`, `hud_debug`, `hud_seq` | `client/cl_hud.qc:896,902,991,6002,6004-6005` |
| `hud_net` | `client/cl_netmon.qc:126,215` (`NM_Frame`; `NM_Draw` uses `nm_cv_on`) |
| `hud_trainer` | `client/cl_trainer.qc:1355,1097` (`Trn_Draw`) |
| `hud_boarding` | `client/cl_boarding.qc:69,116,186` (`Boarding_ReadCvars` / `Boarding_Draw`) |
| `hud_specby` | `client/cl_spectate.qc:63,702-708` (`Spec_DrawWatchers`, not all spectator state) |
| `hud_banner` | `client/cl_banner.qc:70,1164` (`Banner_Draw`) |
| `hud_results_toast` | `client/cl_results.qc:215,859` (creation guard, not modal card closure) |
| `hud_trail` | `client/cl_trail.qc:124,473-474,595-598,610` (`Trail_Frame`, `Trail_Pin`, `Trail_Draw`) |

The bounded inventory of the 66 QC units listed by `src/cl_progs.src` found no
exact quoted literal for the six historical absent names. That is corroboration,
not proof excluding dynamically constructed names or other VM/engine state.
Existing real `hud_crosshair`, `hud_chat`, `hud_strafe`, `hud_keys`, `hud_speed`,
engine crosshair/notifications, `zone_draw`, PVS and input settings stay mandatory.
`hud_energy` is not a catch-all suppression switch. QC `AGENT_NOTES.md:5054-5065`
records an earlier ordinary failure with timer/mapinfo/mouse-pad still visible
behind guessed names, motivating real controls rather than aliases.

## Limitations and remaining gates

The historical failed attempt had 36 real values and six Unknowns, but no
readbacks for these 13 additional controls. Its failure/closure evidence remains
external artifact evidence, not a public test golden or a successful capture.
The original actual capture gate has **not** been integrated with this module;
its six-name value requirement is not changed here. No new adapter, native retry,
refreeze, rendering, cache-functional or performance acceptance follows.

Exact executable subject-progs lineage is **unknown**: held QC source, matching
observed binary hashes, or embedded cvar-name bytes do not prove which source
produced/executed the subject instructions. Authoritative source-to-progs lineage
remains required before native authorization.

Even all 13 additional zeroes do not close the full modal/event/idle overlay gap.
QC `client/cl_main.qc:1671-1726,1765-1851` has two HUD paths plus timer, mouse,
chat, banner, vote, replay, spectator, results, scores, inspector, HUD editor,
zone editor, linegraph, popups and resume-offer paths. `HUD_DrawSubmitWarn` is
unconditional at `client/cl_hud.qc:5988`; `Timer_DrawResumeOffer` at
`client/cl_timer.qc:1279-1289` depends on a resume key, not `hud_timer`. An observed
startup `run_resume=0` does not prove all modal/event/idle states closed. Those
states must be tied to the authored fixture and exact executable lineage, with
actual visual evidence; settings-only output cannot establish a blank overlay.

Renderer/model/material/actor/camera/PVS/branch/worker/GPU/phase/closure gates
remain separate mandatory checks. Their integration and the additional real HUD
readbacks are not yet done in the actual gate. No existing actual control may be
relaxed to Unknown or replaced by fabricated zeroes to obtain a pass.
