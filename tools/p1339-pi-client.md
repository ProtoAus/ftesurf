# P1339 qualified Pi client source

Base: current deployed P1341 Pi source `68597668`, not current main's different
server/client profile. Feature implementation: `2d82c278` on current Windows
baseline; the ramp/snow modules and model bytes here are exactly that feature.
Only the console/callback hooks are adapted to this profile's existing callers.
No main-only features, SSQC/shared stat protocol, native, menu or config changes.
The old GA_Command() signature is preserved (main's has a different signature).

Three VM compile: zero warnings. Native real dedicated test uses this profile's
own SSQC/CSQC; all14 actual HTTPS/consent/refusal/hash/cache/material checks pass.
Largest PNG/mesh native test on the identical feature implementation also passes
with 2048x4096, 17,833triangles, native picture limit131072 unchanged. Main's
reccheck949/0 and corpus548/351historical faults do not claim native verification.

This is source qualification, NOT proof of a live fleet. P1339's main receipt
records actual package hashes, unchanged dependencies and guarded delivery.
