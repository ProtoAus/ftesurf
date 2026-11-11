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

Start from an inspected clean checkout containing this tracked patch. Read the
workspace lifecycle instructions first. Place the EMPTY output under a uniquely
owned task root, create its `OWNER.md` before population, then set `out` below.
This invokes standard Git, not a copied deployment framework or the shared index:

```python
from pathlib import Path
import hashlib, os, subprocess
repo = Path.cwd().resolve()
out = Path('C:/FTESurf-worktrees/<your-owned-task-root>/fetch85')
assert (out / 'OWNER.md').is_file()
ref = '69985a46cc28869558e95d63a2c28ec9169a5928'
hash256 = lambda b: hashlib.sha256(b).hexdigest()
raw = subprocess.check_output(['git', '-C', str(repo), 'show', ref + ':surfd/mapwatch.py'])
patch = repo / 'tools/p1502-mapwatch-fetch85.patch'
assert hash256(raw) == 'bbaf3ed7bd2362a53d4fcd6dd852a0b9968f0de8fd75e7385f8c5b39fd4d7c9f'
assert hash256(patch.read_bytes()) == '498a26dfca83cba29dd000a55ef704bbce9572f15cbdc10f8eaa5b75399be31b'
(out / 'surfd').mkdir()
(out / 'surfd/mapwatch.py').write_bytes(raw)
env = os.environ.copy()
env['GIT_CEILING_DIRECTORIES'] = str(out.parent)
for flags in (['--check'], []):
    subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                    'apply', '--no-index', *flags, str(patch)], cwd=out, env=env, check=True)
assert hash256((out / 'surfd/mapwatch.py').read_bytes()) == 'f62e0810f3626de5d66d6df2130d53efdd907928a7c0bb87cb4a3e75c03d825c'
```

## Verification and limits

Standard `git apply --check` and application reproduce the exact independently
reviewed artifact. The first Windows invocation inherited global autocrlf and
produced CRLF bytes:177538 instead of173959. That checksum refusal is retained,
not a pass. Repairing the invocation with explicit LF gives the exact raw hash;
no post-proof normalization or weakened comparison was used.

Independent compatibility review confirms exactly three retained serving hunks
and otherwise identical public AST. An acted lease-unset positive and configured-
lease pre-lock/run refusal pass; the Windows watcher suite has0 failures with
explicit platform skips. An initial POSIX attempt on DrvFS refused mode511 and
is NOT Linux qualification. Native POSIX/runtime/dependency, real input/census,
current-data preservation/fallback and privileged-profile qualification remain
separate deployment gates. No native/QC Build, mover, service or map admission
change is made by producing this artifact.
