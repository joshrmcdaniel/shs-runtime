# SHS Runtime

This is an experimental compatible engine for Surviving High School. Users
supply the Android 1.0.9 APK and additional EXP episodes. `shs_runtime` executes
original KiWi bytecode and renders user-supplied resources. It is not a static
ARM recompilation or a Ren'Py conversion.

## Build and verify

```sh
uv sync --locked --extra desktop
uv run --locked --extra desktop python -m unittest discover -s tests
uv run --locked --extra desktop shs
uv run --locked --extra build python tools/build_desktop.py
```

Tests use authored fixtures. Optional original-content checks skip when a
player's local content is absent. Do not add original assets as test fixtures.

## Architecture and contracts

- `content.py`: validated EXP/APK import, exact resource IDs, relocatable
  libraries and separation of APK versus episode resource banks.
- `decode/bytecode.py`, `vm.py`: lossless KiWi representation and real VM
  execution, including pending argument frames and callbacks.
- `engine.py`, `runtime.py`: host services, panel state, clocks, choices,
  mini games and versioned JSON saves.
- `application.py`, `desktop*.py`: launcher, menu and pygame rendering/input.
- `fonts.py`, `ui_assets.py`, `atlas.py`: native asset and layout contracts.

Follow SCHEMA.md, VM_SPEC.md and docs/ENGINE_ABI.md. Unknown services must
remain explicit stops with their pending arguments intact. Never invent a
score, result, scene link or random value to bypass them. The heuristic AST
parser and Ren'Py experiments belong to the original research project.

Preserve the 1:1 target: original positions, font metrics, portrait masking,
pagination, panel lifecycle, input gates, timers, randomness and script-visible
side effects. Recover behavior and presentation together. Use Android 1.0.9
as the available reference for the reported identical iOS/Android interface.
Keep unverified details explicit in the specifications.

Do not bundle APKs, EXPs, extracted art/audio/fonts/scripts, native
decompilations, screenshots, generated games, player libraries or saves.
Keep MANIFEST.in and package discovery restrictive. Preserve the inherited
MIT license and attribution in docs/PROVENANCE.md.

The owner handles Git initialization, commits, remotes and pushes. Creating
this directory does not authorize publishing it.
