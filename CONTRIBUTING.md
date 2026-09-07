# Contributing

Build instructions are in the [README](README.md). This file is the set of
things that will bite you, in rough order of how much time they cost.

## ⚠ Never run `git clean -x` in this tree

**The repository root is also the live game install.** The `.gitignore` is an
allowlist, so roughly 3.3 GB is *ignored* — including your compiled engine, the
mounted-game extraction cache, your screenshots, and `ftesurf/data/runs/`, which
is your recorded times. `git clean -x`, `git clean -X`, `git stash --all`, or
GitHub Desktop's "Discard all changes" will delete all of it without naming any
of it.

If you want a scratch tree, clone somewhere else and deploy into your install.

## Set your commit identity before your first commit

```
git config user.name  "<your handle>"
git config user.email "<id>+<handle>@users.noreply.github.com"
```

This is a public repository. Without the override, git uses your global config
and bakes a real name and personal email into every object, permanently.

## The `.src` ordering is load-bearing

`cl_progs.src`, `sv_progs.src` and `m_progs.src` are compile-order manifests, and
QuakeC needs a global to exist before the file that reads it. Every non-obvious
position in those files carries a comment saying what constraint put it there.
**Read the comment before moving a line.** If you add a file, say in the manifest
why it sits where it does.

## `cfg/default.cfg` is a ruleset, not a config

With `cvar_lockdefaults` on, every `set` in that file is the *enforced* default.
Changing a movement value there changes the game and invalidates recorded times.
Treat a physics change as a versioned ruleset change, not a tweak.

The file is also the project's design record — it cites engine source lines and
narrates why values are what they are. Keep that up when you change something.

## `src/defs/*.qc` is generated — do not hand-edit

It is FTE's `pr_dumpplatform` output (engine builtin declarations). Regenerate it
from the engine rather than patching it; see [ENGINE.txt](ENGINE.txt).

## `ftesurf/fs_addons.txt` is deliberately not tracked

The engine rewrites it from its in-memory mount list on every `fs_load` /
`fs_unload`, dropping every comment — and `fs_load <absolute path>` would append
your drive layout into it. The annotated master is
`ftesurf/fs_addons.default.txt`; `ftesurf.bat` seeds from it. Edit the
`.default.txt` if you are changing what everyone mounts.

## Line endings

`.gitattributes` pins LF for everything except `.bat`/`.cmd`/`.ps1`, which are
CRLF because cmd.exe mishandles LF-only batch files around multi-line
`if (...) else (...)` blocks. Don't fight it, and don't "normalise" it back.

## Commit messages

The project numbers its work — `Build NN` for QuakeC, `Patch NNN` for engine
changes — and the engine repo's `ENGINE_PATCHES.md` headings are written as
commit subjects already. Follow that:

```
Build 47 — the strafe widget was reading a usercmd that had just been erased

Root cause: ...
Fix:        ...
Verified:   on surf_kitsune with rec_gh_on 1, 30 runs, no regression
```

Subject ≤ 72 characters. Bodies matter more than subjects here.

## Branches and tags

Commit straight to `main` for anything that compiles and runs. Branch (`try/`,
`wip/`, `fix/`) only for a throwaway experiment, work that leaves the build
broken across more than one sitting, or something you'll want to bisect later;
merge back with `--no-ff`.

Tag builds you'd want back: `git tag -a build-47 -m "..."`. Tags are not pushed
by `git push` — push them explicitly.

**Never rewrite pushed history.** This repository is public.

## The engine pin

FTESurf and the engine move together. When a QC change needs an engine change:
commit and push the engine, tag it, update [ENGINE.txt](ENGINE.txt) with the new
commit SHA, then commit the QC. `build.ps1 -Engine` warns when your local engine
HEAD does not match the pin.
