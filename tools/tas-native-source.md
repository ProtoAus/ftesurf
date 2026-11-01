# Native TAS source components (Patch 1165)

These are **operator infrastructure**, not canonical approval, a public upload
verdict, or a production queue. Ordinary replay does not select preparation from
project/manifest fields. No human recording grammar or eligibility policy changes.

## Components and boundaries

The engine records native searchpath construction and can export a bounded VFS
component: ordered providers, declared ancestry, enumerated logical names, native
lookup winners, content hashes and flat bytes. Opaque/unsupported providers,
ambiguous names, truncation and resource exhaustion fail closed. The Python
`tasvfs` reader independently checks framing, records, winner references, hashes,
flat membership and limits. An export is a COMPONENT, not a complete-world proof.

Readonly asset enumeration has an internal data-open purpose distinct from code
opens. Reading static bytes does not authorize executing scripts/configuration.
Command and server-VM consumers request execution explicitly, independently of
suffix classification. Exported bodies and lookup hashes preserve raw selected
bytes rather than running extension-based decompression. Nonadjacent file/descendant
aliases are refused before bodies are copied. Archive ancestry must have a declared
parent with an earlier construction identity; search order may differ.
Directory/provider declarations and actual opened-file checks remain required;
unsupported provenance does not become trusted through a filename or fallback.
The operator policy is opt-in; ordinary engine filesystem operation is unchanged.

`surfd/tascontent.py` supplies a managed content incarnation/epoch and cooperative
shared/exclusive kernel leases. It does not itself intercept publishers. Missing,
odd or replaced state fails closed. Every real mutation route must participate
before this can protect a canonical observation; initialization alone proves none
of that. Keep an actual snapshot scope through validation, not just its stamp.

## Separate preparation role

A complete static profile can exceed the per-job component budget. The trusted
`ProfilePreparationPeer` is a separate Linux operator API. It requires server
mode, isolated home/discovery paths, explicit native probe/world/private context,
a real borrowed readonly `tascontent.snapshot` description, and a distinct
custody descriptor. Both descriptions are inherited by the native child. The
reader remains locked until native cleanup; it is never unlocked by a borrower.
The Peer checks native descriptor retention and actual executable identity.
Native children also get Linux parent-death setup, including the pre-setup race
check. This does not replace supervising/reaping the actual process.

Limits are fixed in code, not chosen by submitted metadata:

| Domain | Files | Aggregate |
| --- | ---: | ---: |
| Native component export/parser | 8,000 | 2 GiB |
| Native preparation export/parser | 131,072 | 8 GiB |
| Ordinary Peer inventory/dynamic output | 8,192 | 256 MiB |
| Preparation Peer inventory/dynamic output | 132,096 | 8 GiB + 256 MiB |

The native command is `fs_tas_profile_export`, enabled only with
`-tas-vfs-profile-prepare` and `-tas-vfs-probe`; `ProfilePreparationPeer` supplies
the preparation flag. It uses the `TASVFSEXPORT` framing family with the distinct
`profileprep` purpose token and `parse_preparation` entrypoint. The ordinary parser
rejects that purpose, and preparation parsing rejects a component frame. Native
per-file and logical-name caps still apply. Peer retains its ordinary 64 MiB
per-file/log guard, process/address-space limits, static-file checks, symlink
refusal, cancellation and cleanup. A profile with a larger individual asset is
unsupported by this preparation Peer even if it fits the native aggregate cap.

For source probes, canonical `source_base` must be absolute, existing and outside
the owned private runtime. Config/log/generated paths stay in that runtime; HOME
and XDG discovery are redirected there. Ordinary replay retains its private
basedir and `-nohome` behavior. Passing a source path is not source qualification.

## What is still required

A caller must still establish complete source coverage and actual publisher
fencing, preserve execution/data namespaces, join source and private-view identity,
bind native images/QC/map/zone/tick/physics/permissions, and demonstrate an actual
legal canonical finish. Qualification and promotion require their own evidence.
Do not use synthetic exports, passing grammar tests, an epoch file, or a prepared
static profile as a canonical permit. This patch does not enable a service or
change public submission admission.

Focused checks are `tools/test_tasvfs.py`, `surfd/test_tascontent.py` and
`tools/test_tasverify.py`. POSIX-only skips on Windows are not Linux acceptance.
Reviewed source passes28/7/42 tests on each platform (Windows skips3/6/9;
Linux skips only the Windows-only managed-content case). Acting ARM checks cover
execution purpose, raw compressed bytes, alias refusal and a real BSP/QC trusted
entfix edit. Human reader tests remain949/0 failed; a paired541-run corpus sweep
retains348 existing faults in both readers. These are component regressions, not
full source-profile qualification, queue admission or deployment. An isolated real
native preparation smoke also confirms component/preparation byte equality,
cross-role reader refusal and the actual inherited shared-reader lease: a writer
remains blocked after the parent's test-only early close until native cleanup,
then acts and advances the epoch. That does not establish real publisher coverage.
Final-image and deployment acceptance remain separate from source tests and
compiler invocation.
