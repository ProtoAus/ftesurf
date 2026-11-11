# P1505 defensive identifier token extents — development delivery

Engine `08c5cc387fcad4b79c8db0e2832d2d40e9372a5b`, annotated tag `patch-1505`;
QC pin `2f17c781b22f2c8a5235402cc53dc2caa73ddd49`. Both exact inspected source
commits were pushed to their repositories' main branches. Build remains 89.

## Change and verification

Both ordinary identifier bytes and malformed-text diagnostic bytes reserve the
final token terminator, using the existing compile-fatal handler. Accepted
identifier syntax, UTF8 decoding, diagnostic behavior within capacity and the
smaller language-level declaration-name limit are unchanged.

- Independent bounded source review: no remaining findings. The ordinary scalar
  declaration route was separately traced before long-name production controls;
  maximum token capacity does not imply all downstream routes accept that name.
- Final and actual installed compiler: 20 production controls, including eight
  accepted ASCII/UTF8/boundary cases with decoded scalar value checks, preserved
  existing language-limit refusals, and acting extent/fatal-context refusals.
- Eight fitting predecessor counterparts match decoded global values/types,
  CRC and diagnostic payloads. This is not whole-DAT byte equivalence.
- Forty-two source-bound observations use the exact scanner and production UTF8
  decoder. Original invalid stores are intercepted before out-of-object access;
  the overly strict mutant rejects the valid boundary, and canaries are intact.
  These are scanner controls, not untreated malformed old-compiler execution or
  full-compiler mutation tests.
- Full Windows client/server/five-plugin build: all 74 warning payloads match the
  like-mode predecessor. Clean standalone compiler: six matching warning payloads.
  No new warnings; all three QC programs compile without warnings.

## Native-only installation

Promotion: **2026-11-11T12:32:08Z**. Readback: **12:32:46Z**.

- Seven native images in each Windows install, plus the existing canonical
  developer compiler: 15 target, `.prev` and independent rollback hashes verified.
- Both actual clients identify clean `patch-1505-0-g08c5cc387` source.
- All 21 protected existing-file/absence guards unchanged, including game
  programs, owner/default configs, manifests and the non-target client alias.
- No owner/peer process killed; no progs, lobby, backend, config, player-data or
  release swap. Earlier rollback preimages are retained separately.

Client SHA-256: `5be0c6a5e571f30258a44f523465c49b103623740cd268f63ed0b48e0effcf1d`.
Standalone compiler SHA-256:
`1f2efd0616f60e2c3d29372cb7c32f8cad1f15cb0831d8e2490e5468048550bc`.

This is compiler safety maintenance, not exploitability proof, a new detector,
a full parser audit, ARM/lobby native deployment or anti-cheat-plan completion.
Further independent parser work continues; existing unrelated blockers remain
separate. Original failed/superseded tooling receipts are retained privately.
