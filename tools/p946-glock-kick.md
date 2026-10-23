# P946 — finish the requested pistol recoil coverage

Reserved946 after fetching both repos/max945 (headings + untracked claims).
Bases QC5ba6f546/engine85d1d9e86, existing exclusively owned source-polish root.
Canonical peer dirty source/index left alone; only own small reservation file.

Final scope review caught P943's WP_Bullet impulse branch was USP/Scout-only.
The request said pistols, so Glock belongs too. Not permission to end at943.
Change is ONE else-if: Glock adds54.365635 to upward pulse velocity, half the
USP/Scout impulse108.73127. Isolated analytic peak1degree; each actual WP_Bullet
gets it, including both burst follow-ups. No guessed ballistic/spread/ammo change.
Shared exact critical damping and temporary VF_ANGLES/restoration remain; raw
VF_CL_VIEWANGLES, body, input, SSQC, protocol, recorder/collector and native binary
are untouched. Existing FOV/preferences/bindings and other weapons unchanged.

## Actual controls, not silence

Existing P943 native combined log's2026-10-23 19:56:15 lines have Glock burst
ACTED, client mode1/pending0/kick0/velocity0, server projectile counter6. Isolated
excerpt artifacts/p946-control943.txt preserves it; code branch also excluded8.

New dedicated native socket, ordinary Momentum Axiom (no local CSS map fixture),
960x600, cl_maxfps100/cl_idlefps0/cl_nopred0; SFX deliberately0 to prove kick does
not depend on sound. Commands/camera diagnostics and complete logs retained:
- Single: client1/server1, mode0; kick-0.982692 then-0.494454, then-3.53937e-12.
- Burst after toggle: total client4/server4 (=three new), pending0; kick-1.93883
  sample, then-2.96065e-11. This is a SAMPLE, not measured burst maximum.
- USP: actual new shot5, kick-1.96424. Two-degree control still acts.
- Knife: actual shot6, kick0/velocity0. Melee did NOT acquire pistol recoil.
- Every diagnostic stored render-angles0/input-angles0; scene-only pulse state
  is nonzero. No aim/body motion, source or playback evidence claim from this.
- Real render delta varied .0079..0477s; do NOT call this steady100Hz/1000FPS.
  Existing P943100/1000Hz analytic proof applies by linear half-impulse scaling;
  damping code unchanged. Human recoil strength/feel is pending lextest.md.

Build3VM0warnings, QW/MENU exact943 bytes, ONLY CSQC changes. After commit, clean
rebuild must reproduce exact candidate before promotion; final source/hash/fleet
and cold served-code availability in p946-delivery.md. No new release/Build,
map/player data, owner process/config, native or backend deployment authorized.

Owned actor weapons946 stopped normally after controls. Lighting remains the
separate documented P943 matched-view human question; this patch makes no shader
claim. Prior canonical P943 same-name untracked reservation was verified ours,
its original retained in artifacts and only that owned claim retired to avoid
shadowing the now-published controls document. No foreign claims/files cleaned.
