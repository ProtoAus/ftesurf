# Explicit native inputs for historical ImGui harnesses

The p598 builder, p600 input, p601 model, p603 scoreboard/performance and
p603 font/dense control-source CLIs no longer select personal development
worktrees or an installed dedicated server implicitly. Those defaults kept
obsolete checkouts looking like permanent dependencies and could silently mix
client/server cohorts. This is tooling only, not a product patch or new runtime
acceptance claim. Historical commands, results and graders are unchanged.

## Select inputs deliberately

Select the engine source revision required by the historical arm in a new owned
checkout, and build/qualify its binaries separately. Then pass that source root:

```powershell
python tools/p600input.py --fte C:/owned-engine-source run
python tools/p598build.py --fte C:/owned-engine-source --host --out C:/owned-task/native-host
```

`--fte` also accepts an explicitly set `FTESURF_FTEROOT` environment variable;
the command-line flag takes precedence. Without explicit executable overrides,
the client/server resolve to `engine/release/fteqw64.exe` and
`engine/release/fteqwsv64.exe` **under the selected root**. `--engine` and
`--server` override those paths independently. No canonical or retired checkout
is a hidden fallback. Build/control-source commands require a selected source.

Already qualified prebuilt runs can instead supply `--plugin`, `--engine` and
`--server` together without selecting a source checkout. The performance tool
already requires its prebuilt plugin/VM artifacts. Existing baseline controls
(`--old-engine`, `--input-engine`, `--old-plugin`, etc.) still require the
historically appropriate explicit overrides; this change does not reinterpret
or rebuild them. Missing subject selection is rejected before any rig/build
entrypoint is reached.

Grade-only forms (`grade <rig>` or the scoreboard's `--grade <rig>`) and `--help`
need no native selection. Reading retained evidence does not compile or launch
anything. Path selection itself does not prove that files exist, that a binary
matches a source pin, or that a historical control/subject pair is valid: retain
and inspect the normal source/binary hashes and actual acting controls.

## Validation scope

```powershell
python -m unittest discover -s tools -p test_native_test_paths.py
python -O -m unittest discover -s tools -p test_native_test_paths.py
```

These are parser/path-selection and CLI dispatch tests, not game acceptance.
They execute each real main-block parser/dispatch with native/build/copy
entrypoints replaced by refusing stubs. Existing grade success/failure results
must be preserved. Environment/flag precedence, explicit prebuilt inputs,
matching client/server derivation, missing-input refusal and portable help/grade
are covered. Separate real subprocess smoke checks cover help and missing-input
rejection. No native compiler, game/GPU, live install or deployment is needed.
