# P1503 defensive numeric token extents — development delivery

## Source and scope

- Engine: `778632bfdac495c7471cd05627673efe273691a9`, tag `patch-1503`.
- QC pin: `e1ec728620e8c13b4a6501501e1291ebae0c3f83`.
- Both inspected commits were pushed by exact SHA to their repositories' `main`.
- Numeric token appends consistently reserve the terminating byte and use the
  existing compile-fatal error path. Accepted syntax, conversions, suffix/type
  branches and dispatch are unchanged.
- Build remains 89. No gameplay, recorder/reader format, capture, consent,
  scoring, enforcement, default, backend or account-policy change.

## Verification

- Independent frozen-source review: no remaining findings after correcting the
  initial error-path choice to the compiler-fatal handler.
- Final clean standalone compiler: 64 production controls (33 acceptances and
  31 clean refusals); four additional function-body/source-list error controls.
- Corresponding fitting predecessor controls agree on decoded global values,
  complete vectors, CRC and diagnostic payloads. This does not claim whole-DAT
  byte identity or a type-sensitive oracle for every intermediate literal type.
- Source-bound helper controls distinguish the removed and over-strict guard
  before an invalid store and preserve the instrumented buffer canaries. These
  are helper controls, not execution of every original scanner under mutation.
- Full supported isolated Windows build: client, dedicated server, five default
  plugins and all three QC programs. QC: zero warnings. Native: the same 74
  warning payloads as the predecessor. Clean standalone compiler: the same six
  warning payloads as its clean predecessor build; no new warnings.
- All 5,882 reused dependency files were byte-identical after the builds.
- Compiler revision metadata is supplied through the supported make variables,
  using the same Windows Git view as `build.ps1`; final compiler and client
  stamps identify clean `patch-1503-0-g778632bfd` source.
- Original failed fixtures, probes, comparator assumptions and superseded
  candidates remain in private evidence; none is reclassified as acceptance.

## Installed state

Native-only promotion completed at **2026-11-11T11:54:20Z** through the pinned
`build.ps1` `Deploy` function. Installed readback at **11:54:45Z** verified:

- Both Windows clients, both dedicated servers, all five plugins in each
  Windows install, and the existing canonical developer compiler: 15 targets.
- Every target's SHA-256 and its `.prev` predecessor, plus independent rollback
  preimages. Earlier `.prev` images were separately retained as well.
- Both actual client executables report clean patch-1503 source.
- The actual installed compiler passes all 64 numeric and four error-context
  production controls.
- All 21 protected existing-file/absence guards, including game programs,
  owner/default configs, manifests and the non-target client alias, unchanged.
- No owner/peer process killed. No QC program, lobby, backend, configuration,
  release or player-data deployment was performed.

| Image | SHA-256 |
| --- | --- |
| client | `77a665664a1c1c8d25ecfd03e224e38ee5dea132809799449d9609b520918efb` |
| dedicated server | `a22a6e6cdc7c44e2bb10b7f3635d8f82cda220215c19483d96920c7d82f4c629` |
| hl2 | `4ad07bb5e89f9b9c5a29c5e3840e83cf061161489d7b831b2322422aec74e9c2` |
| cod | `bce99654f6a53f9d5b91350405af5879c7d6b50d5148030fb81abdb55333d2d8` |
| box3d | `b45b4a6acebbceafd31bd55242e963cfb383062bd39d6f3cb5b571de1649d488` |
| ode | `d899cd11b9f391ff49105fe6d56ccca564b7efdd089f07274a96f99b17047abf` |
| ui_imgui | `877815194d86155566cd8c4d8f32e493e63630b4690c2206c893deb52a340ccb` |
| standalone compiler | `86f9f9b4a69725d435e365862771a957ef47df7392a3b7781cbded1fbb0cdfd2` |

## Limits

This is a compiler extent correction and its Windows development delivery, not
an exploitability result, new detector, ARM/lobby native deployment, complete
parser audit or completion of the broader security/anti-cheat work. Existing
unrelated blockers and human-only acceptance questions remain separate.
