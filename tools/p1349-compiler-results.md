# P1349 — truthful developer compiler results

## Change

Failed required primary-program or requested debug output now uses the existing
compiler error/unwind path instead of returning overall success. Legitimate
empty/no-output completion remains distinct from failure. A missing optional
decompiler now reports its unavailable capability before configuring or calling
that interface. Existing untrusted-command refusals remain ahead of those effects.

This changes no recording or evidence grammar, input capture, comparison policy,
VM layout, Build number, or release. Requested debug-output failure can follow an
already accepted primary file; this is not atomic multi-output acceptance.

## Published source

- Feature/tag: `cbbe4b48766321b30d91011ec519f32bcbef0988`, `patch-1349`.
- Integrated public source: `8e389dc4beabd8247e888dbf243e11d7b3ebbbaf`, retaining
  the newer published P1348 client corrections rather than overwriting them.
- The original ARM images actually come from `cbbe4b487`; they are not relabeled
  as built from the later integration commit.

## Verified scope

- Two independent product-source reviews covered compiler unwind/results and
  capability/command provenance, with no findings in their assigned scopes.
- Sixteen actual in-memory compiler cases per platform on Windows and ARM,
  including positive output, primary/debug refusal, parser error, and independent
  correction-removal controls. Safe actual-handler controls also distinguish
  absent capability, valid calls, and existing untrusted refusals on both.
- Initial clean Windows client/server and ARM dedicated-server/paired-plugin
  builds add zero warning sites. Windows retains 74 native warnings and the same
  two known QC warnings in nonshipped NoDeploy output; ARM retains 16 server and
  one plugin warning.
- Each initial native image passes 1,578 checks and reaches the intended
  unavailable-decompiler diagnostic. An actual archived known-PASS native verifier
  smoke also matches its control with fixture and test-program inputs unchanged.
- The later public integration changes only four client C files and the journal.
  Complete dedicated-server/plugin input closures exclude all five: 132 server
  objects/dependency manifests and 13 plugin translation units, with 285 tracked
  inputs unchanged. Original ARM evidence and images therefore remain valid,
  with their original source/version identities.

These checks do not establish real filesystem-failure handling, full VM ABI or
all configurations, allocation balance, asynchronous compiler lifecycle, GPU
performance, visual/feel acceptance, or whole native-audit completion.

## Delivery status

**Integrated Windows native update delivered to BOTH installs on 6 November
2026 at 17:14:20 UTC; Pi native activation remains blocked.**

A later execution boundary recovered above the unchanged 4 GiB physical-memory
gate. The exact existing clean FullNative/NoDeploy procedure then built source
`8e389dc4beabd8247e888dbf243e11d7b3ebbbaf`; no earlier incomplete client image was
substituted. Complete raw-log comparison retains the same 74 native warnings and
two known nonshipped QC F333 warnings, with no new diagnostic sites. All seven
native outputs were frozen with their actual integrated version. Both executables
passed 1,578 native checks and reached the unavailable-decompiler handler.

The existing guarded native-only copy updated the ten actual build-procedure
targets across `C:\FTESurf` and `C:\FTEQuake`, preserving every destination's
predecessor in `.prev` and retaining prior-`.prev` preimages separately. A game
started after the copy and blocked the final inventory; that wrapper failure is
retained, not mislabeled a clean transaction. No process was killed and no copy
was repeated. A later idle, read-only postflight completed with all destination,
`.prev` and frozen hashes exact and zero changed, missing or new protected files
outside the copy set. QC programs, configs, player data and other aliases were
not shipped. This does not claim fresh graphical, FPS or owner-feel acceptance.

The ARM transaction reached actual guarded preparation. Eight recorder parts and
183 complete current-resume preimages were individually verified on and off box,
as were all four current native/plugin and prior-`.prev` images before canonical
staging. Twelve real announcement transports succeeded, followed by a measured
10.000226-second grace period. This is transport evidence, not proof every player
saw the chat.

The locked preservation check then refused a changed recorder namespace before
any live swap or restart request. The original failure is retained; it is not a
successful deployment or permission to replay the failed transaction. Postflight
verified all four original current/`.prev` identities and bytes unchanged and
retired only the four verified transaction-owned staging files. No gate remains
held and no player data was restored or removed. A later observation again found
the original eight parts and no open preserved-namespace handles in the thirteen
declared actors; it does not reconstruct the transient change at refusal time.

Both operational-review findings were fixed and independently rechecked: warning
freshness at each individual rename/restart boundary and enforced four-image
OFFBOX custody before staging. Their acting synthetic controls are separate from
the actual transfer, announcement and refusal evidence. Backend, configs and live
VM payloads were not changed by P1349.

A subsequent read-only prerequisite check found nine parts against the archived
eight, one open preserved-namespace descriptor, and a snapshot changing during
the read. All four canonical images and thirteen actor identities still matched;
the 183 complete resume rows also matched. A later diagnostic saw no open
namespace handle, which does not establish a stable eligibility window or
reconstruct the original refusal. No recovery allowance was consumed and no
same-baseline recovery was implemented or attempted. A controlled closed-recorder
handoff and explicitly approved fresh preservation context are needed before
another rollout; the failed transaction and every original archive remain intact.

At 17:18 UTC a new read-only observation again matched the original complete
parts/resume namespace, canonical images, actor identities and backend bindings;
no preserved-namespace handles were open and the read was stable. The original
on/off-box archive and all four predecessor images were reverified. This later
observation does not reconstruct either earlier refusal, reset the failed
transaction, establish a future safe window, or authorize replay. No same-baseline
recovery interface or allowance has been used. A separately explicit, single-use,
proof-bound recovery decision remains necessary before Pi mutation; retain the
original failed receipts, baseline, archives and retirement history.
