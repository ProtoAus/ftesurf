# P934 — native bindlist

Type `bindlist` in the local console. The output has alphabetically sorted key
names and quoted commands, including modifier overrides and separate alternate
bindmap groups. Inherited modifier copies are collapsed (same command AND same
execution level as base), rather than displaying eight copies of every normal
bind. Nonlocal execution levels are printed. Empty/unbound entries are omitted.
The command does not change, execute, save or export a binding. Insecure callers
are rejected before enumeration; that guard is source-reviewed, not claimed as
a new remote-server runtime acceptance test.

## Controls and evidence

`tools/p934bindlist_smoke.py` uses p615link's owned overlay and an isolated
synthetic configuration. It never reads/dumps the owner's bindings or sends keys
to their process. All owned clients are stopped and shared-content links unlinked.

- Old client: fixtures ACT via bind queries, but `bindlist` is unknown.
- New client: seven entries; base keys sorted; Ctrl+a override, F5 level30,
  compound quoted MOUSE3 command, and Bindmap2 MOUSE1 all present.
- Saved binding directives before/after are identical in both arms.
- After unbindall, subject reports zero entries.
- Initial subject assertion expected level31. Existing bindlevel clamps to
  RESTRICT_MIN30, so the fixture was corrected to30. No product fix was needed
  and the failed arm remains retained, not counted as a pass.

NoDeploy native build through the existing build.ps1 -Engine -NoDeploy -FteRoot
entrypoint succeeded. keys.c had no warnings. Untouched ODE/mathlib warnings
remain in the full build log; this is zero NEW warnings, not zero TOTAL warnings.
Regenerated clangd's database (229 m-rel translation units) using tools/clangdb.py
--engine. Initial fallback LSP diagnostics lacked shader.h; native build and
runtime controls, not that incomplete fallback, establish compilation/behavior.
The generated mat_vmt_progs.h difference is only its generator-path comment;
it is not a shader/product change and is not included in this patch.

Clean native source is f76bd37bfee96521c4d845dc16da5bba1af5ef8b, tag patch-934.
The first incremental clean rebuild reused an older object stamp despite new
SVN_VERSION flags; rejected it for promotion and preserved that log. The
supported -Full rebuild produced actual stamp git-7719-patch-934-0-gf76bd37bf,
SHA256 aac1ba40893e63e13f46182e20e0540ff5a4a5365abc975668eaaaa64a051848.
A broad stamp regex initially captured an adjacent sentence's period; a bounded
source-stamp regex verified the existing valid artifact without another rebuild.
The clean-stamped client then passed the seven-entry/sort/immutability/empty
runtime suite. Final LSP diagnostics are only two untouched warnings (lines22
and1872), no errors or diagnostics in the new code. Both Windows client images
matched that SHA256 at2026-10-22T18:39:58Z, with predecessors preserved. Owner's
running game was left alone; next launch loads the command. No server/plugin
binary was replaced. Full combined delivery provenance: tools/p933-delivery.md.
No Pi server/native or unrelated producer promotion is part of bindlist. A
running owner's client is never killed or restarted by the agent; new native
code takes effect on their next launch.

## P933 and download observations

At the initial P934 install, P933 backend/fleet promotion was still pending.
That is now superseded by the combined compatible delivery in
tools/p933-delivery.md: QC49a1078a and backendcc0b7ffa preserve P932 and add
P933 without changing the independent held producer/native cohort. Full staged
suite, guarded OPEN/schema20/fresh worker, all12lobbies and an exact cold-client
CSQC download/acted command are verified. Real-account Stage/Bonus/join/profile
appearance remains owner-only pending, not inferred from deployment.

P933 QC f58269636a521cdcd4c26fe87495790fd6241951 and engine-log
15c32d096ff5adc38ff7f8dcbaeb3b325619a200 are pushed. At
2026-10-22T18:09:31Z all six generated dat/lno files matched in both Windows
installs, with .prev retained (and earlier .prev copies preserved). Key hashes:
qwprogs 3603c36d9fbe52cbd2e6aebcd345e9ac4a584af5f59a1d5bc480dc6b44ab4f39;
csprogs 7aa55a08f082063dd52673842a71d55f5c4b06b130568a1d3c7b4e2c5e95b1d4;
menu b03c7155227003b4962b2323a115e74e8010d8e2657c8a484ff37c4270497f1d.
A first local promotion wrapper assumed the wrong builder variable/helper; the
actual builder had already succeeded and copied the second install. Inspected
the real Deploy function, reused those valid artifacts, preserved .prev and
verified the canonical copy. No peer working-tree source/config/data shipped.

At 2026-10-22, a bounded public surf_demise BSP request returned302 directly to
R2 (signed URL withheld). A 2MiB byte range returned206, Content-Encoding
identity, in0.266s (about7.519MiB/s). This proves that observed HTTP R2 route is
not capped at1MiB/s, NOT a full-file integrity test or engine-client throughput
claim. Gateway redirects bulk traffic away from the Pi. The1MiB/s rate in
r2gateway.nginx applies only to the local fallback; it is not removed or confused
with R2's path. Maps are mirrored as their exact BSP bytes, not newly gzipped by
this mirror/gateway. The observed BSP response was uncompressed.
