# P1571 — appearance tables remain compatible with installed updaters

## Problem

The authored average-colour and per-map unshipped-material tables were placed
under `ftesurf/data/`. Released updater policies deliberately manage only named
public snapshots there, protecting player data. Adding exceptions only to new
readers cannot deliver a new reader through an old one.

## Change

Produce, load and explicitly ship `scripts/matcolours.txt` and
`scripts/unshipped.txt`, within the existing managed asset namespace. Restore all
three production policies exactly: publisher, native C reader and Rust launcher.
Do not migrate/delete the old DATA files or broaden any DATA prefix. Existing
missing-table/defaultwall and missing-content-warning behavior is unchanged.

Engine: `ca46327b755db85fdb2fc75b533e5863ee256e3d`, tag `patch-1571`.
The normal default/ranked movement, wire formats and qcbuild89 are unchanged.
Unfinished Native movement variants are not part of this change.

## Verified

- 21 publisher tests pass, including signed-object round trips with the two
  scripts assets and rejection of the corresponding old DATA paths.
- Actual released-source C and Rust policy controls accept these scripts assets,
  reject their old DATA paths, and keep player files, unsafe paths and flags
  refused. Prefix-omission controls demonstrate the positive checks act.
- Independent final source review found no remaining blocking issue.
- Exact cheap release preflight passes, including literal assets and 33 patch
  notes for the proposed 0.1.46 update.
- All three release-version QuakeC VMs compile with zero warnings.
- Windows public-default full client/server/five-plugin builds pass. Final
  release build uses the complete SDK from the previously published release,
  not an incomplete development cache which silently links MSYS DLLs. PE import
  inspection finds no extra development DLL dependencies in the client, server,
  HL2 or UI plugin; source and reused SDK remain unchanged.
- Linux client/server/HL2 build at the exact engine pin passes all four gates,
  including the supported glibc ceiling and dependency restrictions.
- Actual Windows plugin qualification, before the final static-library rebuild,
  proves both scripts tables ACT: changing the colour changes the resolved
  shader, a matching map suppresses only the intended warning, a wrong map stays
  loud, and absent tables restore defaultwall and the old warning. Both legacy
  DATA paths are absent throughout the runtime search path. This uses a small
  local asset fixture, not a distributed map or new product instrumentation.
- Final clean static client/HL2 images pass a separate fresh-fixture smoke with
  no development DLLs present. Both scripts tables ACT again: the distinctive
  colour reaches the resolved shader and the matching census is suppressed.
  The finite client exits normally and its owned process/descendants are gone.

## Limits and publication boundary

Source/policy and bounded loader qualification are not full gameplay, visual,
old-installer or exact final prepared-candidate acceptance. Signed candidate
checks and ordinary prepare-once publication/acceptance remain separate release
steps. Do not change updater trust rules to pass a
packaging problem. Do not advertise unfinished full HL1/AG or HL2 movement.
