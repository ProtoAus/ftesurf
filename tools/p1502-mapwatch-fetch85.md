# P1502 mapwatch artifact for the existing fetch85 source family

This is a source-only build recipe, NOT an installer, deployment receipt,
namespace update, or permission to mutate a sealed generation. The normal
`surfd/mapwatch.py` remains unchanged. Do not deploy an arbitrary latest tree.

The existing fetch85 family has no `tascontent` module. Its historical mapwatch
already refuses a configured `SURFD_TAS_CONTENT_LEASE`, both in the publication
helper and BEFORE locking/downloading. This patch retains exactly those three
compatibility hunks; it does not introduce a permissive optional-import fallback
or disable a configured lease. It is unsuitable for a family that needs that
lease: such a family needs its complete normal source closure instead.

## Exact inputs and output

- Public source commit: `69985a46cc28869558e95d63a2c28ec9169a5928`.
- Input `surfd/mapwatch.py` SHA256:
  `bbaf3ed7bd2362a53d4fcd6dd852a0b9968f0de8fd75e7385f8c5b39fd4d7c9f`.
- Tracked `tools/p1502-mapwatch-fetch85.patch` SHA256:
  `498a26dfca83cba29dd000a55ef704bbce9572f15cbdc10f8eaa5b75399be31b`.
- Generated artifact SHA256:
  `f62e0810f3626de5d66d6df2130d53efdd907928a7c0bb87cb4a3e75c03d825c`.

### Independently compatible reader build

A legacy reader is not automatically a safe rollback reader for new sidecars.
The old four-field reader knows131 selected Beta IDs in the original corpus but
only2 in the new typed-sidecar fixture:129 existing bindings are lost and47
nonprefix rows refuse. Keep the new data-format reader in any relevant fallback.
The independent reader artifact uses P1496, not the P1502 scoped-import subject:

- Public source commit: `45df6d2e49c5190c39f207ce615310ec2fccfeda`.
- Input `surfd/mapwatch.py` SHA256:
  `5298ea3c05dcb905cd7939d4185afe0ae23ad12d9af4bce1c186564fb2c4f1a0`.
- Tracked `tools/p1502-mapwatch-fetch85-reader.patch` SHA256:
  `2ce2dd642e7d871c95c040056c8ef95571c122f05f56e646fbf93aac513f0ea9`.
- Generated reader artifact SHA256:
  `fe9f09fa04cacb1bf6c61e2ebab9b78b9ae445c195649df3083e812590cc7917`.

It retains exactly the same three serving guard operations and otherwise matches
P1496 AST. It has no P1502 scope/copy functions or `--scope` option. The primary
patch correctly refuses on this older input because its adjacent mapmanifest
context exists only in P1502; the reader patch changes only those contexts.
That failed apply is retained, not treated as a passed or weakened check.

Start from an inspected clean checkout containing both tracked patches. Read the
workspace lifecycle instructions first. Place the EMPTY output under a uniquely
owned task root, create its `OWNER.md` before population, then set `out` and
`choice` below. This invokes standard Git, not a copied deployment framework or
the shared index:

```python
from pathlib import Path
import hashlib, os, subprocess
repo = Path.cwd().resolve()
out = Path('C:/FTESurf-worktrees/<your-owned-task-root>/fetch85')
assert (out / 'OWNER.md').is_file()
choice = 'scoped'  # or 'reader'; use a separate owned EMPTY output for each
inputs = {
    'scoped': ('69985a46cc28869558e95d63a2c28ec9169a5928',
               'tools/p1502-mapwatch-fetch85.patch',
               'bbaf3ed7bd2362a53d4fcd6dd852a0b9968f0de8fd75e7385f8c5b39fd4d7c9f',
               '498a26dfca83cba29dd000a55ef704bbce9572f15cbdc10f8eaa5b75399be31b',
               'f62e0810f3626de5d66d6df2130d53efdd907928a7c0bb87cb4a3e75c03d825c'),
    'reader': ('45df6d2e49c5190c39f207ce615310ec2fccfeda',
               'tools/p1502-mapwatch-fetch85-reader.patch',
               '5298ea3c05dcb905cd7939d4185afe0ae23ad12d9af4bce1c186564fb2c4f1a0',
               '2ce2dd642e7d871c95c040056c8ef95571c122f05f56e646fbf93aac513f0ea9',
               'fe9f09fa04cacb1bf6c61e2ebab9b78b9ae445c195649df3083e812590cc7917')}
ref, patch_name, source_sha, patch_sha, artifact_sha = inputs[choice]
hash256 = lambda b: hashlib.sha256(b).hexdigest()
raw = subprocess.check_output(['git', '-C', str(repo), 'show', ref + ':surfd/mapwatch.py'])
patch = repo / patch_name
assert hash256(raw) == source_sha
assert hash256(patch.read_bytes()) == patch_sha
(out / 'surfd').mkdir()
(out / 'surfd/mapwatch.py').write_bytes(raw)
env = os.environ.copy()
env['GIT_CEILING_DIRECTORIES'] = str(out.parent)
for flags in (['--check'], []):
    subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                    'apply', '--no-index', *flags, str(patch)], cwd=out, env=env, check=True)
assert hash256((out / 'surfd/mapwatch.py').read_bytes()) == artifact_sha
```

## Verification and limits

Standard `git apply --check` and application reproduce the exact independently
reviewed artifact. The first Windows invocation inherited global autocrlf and
produced CRLF bytes:177538 instead of173959. That checksum refusal is retained,
not a pass. Repairing the invocation with explicit LF gives the exact raw hash;
no post-proof normalization or weakened comparison was used.

Exactly three retained serving hunks and otherwise identical public AST are
checked for both artifacts. Acted lease-unset positives and configured-lease
pre-lock/run/download/publication refusals pass. The primary Windows suite has0
failures with explicit platform skips. The initial DrvFS mode511 refusal remains
a failure. Later native POSIX tests use the exact matched85-file source family:
primary/P1502 and reader/P1496 suites each finish0failed/0skips. Runtime/external
hash and POSIX metadata closure pass; the shared owned source-only fixture is
restored to exact primary bytes afterwards. No source checkout was modified.

Both readers recognize178 exact selected Beta tuples in a NONCANONICAL merge.
Each sidecar preserves177 unselected literal lines in order, and every unselected
reader semantic field remains unchanged. Native1/2/3 and public0/3 positive arms
act. This fixes the demonstrated legacy-reader boundary, not merely its test.
Real complete source/status censuses, current inputs/canonical merge, actual
current-DATA/operational fallback and privileged-profile qualification remain
separate deployment gates. No native/QC Build, mover, service or canonical map
admission change is made by producing either artifact.
