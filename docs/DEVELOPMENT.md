# Development

See [MAINTAINERS.md](../MAINTAINERS.md) for contributor setup, reporting issues,
compatibility requirements and pull request guidance.

The project is self-contained under `src/shs_runtime`. It does not import
modules from the old decoder checkout or require any extracted game files
to install, test its synthetic fixtures, or build an executable.

## Environment and commands

Use Python 3.10 or newer. From the project directory:

```sh
uv sync --locked --extra desktop
uv run --locked --extra desktop python -m unittest discover -s tests
uv run --locked --extra desktop shs
uv run --locked --extra build python tools/build_desktop.py
uv run --locked --extra build python tools/package_desktop.py --label local --smoke-test
```

`shs-tool` provides `import`, `list`, `play` and `trace`. It can also be invoked
with `python -m shs_runtime`. The desktop entry point is `shs`, or
`python -m shs_runtime.application`.

```sh
uv run --locked shs-tool import --apk /path/to/game.apk --episodes /path/to/Episodes --library /path/to/library
uv run --locked shs-tool list --library /path/to/library
uv run --locked --extra desktop shs-tool play --library /path/to/library --episode "The New Girl"
uv run --locked shs-tool trace /path/to/episode.exp
```

The desktop menu supports adding further episodes to an existing library.
CLI `import` creates a new library and refuses to overwrite an existing one.
`trace` starts an empty engine state and stops at a pending action; it is a
bounded diagnostic, not an automated episode playthrough.

## Architecture

| Layer | Modules |
| --- | --- |
| Content and local import | `content`, `builtin_episode`, `episode_catalog` |
| KiWi decoding and execution | `decode.bytecode`, `vm`, `trace` |
| Host services and saved sessions | `engine`, `runtime` |
| Dialogue, choices and panel clocks | `dialogue`, `choice`, `dialogue_animation`, `relationships`, `loading` |
| Mini games | `minigames`, `word_grid`, `football` |
| Native formats and geometry | `fonts`, `ui_assets`, `atlas`, `menu` |
| Desktop application | `application`, `desktop`, `desktop_*` |

The engine/session state owns script-visible behavior. Rendering must not
silently answer callbacks or change game results. Preserve pending frames,
timer clocks and random streams across save/load, pause and scene changes.
Unknown services remain explicit diagnostic stops.

## Tests and private content

See [Running unit tests](../MAINTAINERS.md#running-unit-tests) for full-suite,
single-file and individual-test commands, filtering options and expected skips.

The default test command works without any game files. For optional checks,
follow [Testing with your own game files](../MAINTAINERS.md#testing-with-your-own-game-files):
place your APK at `surviving-high-school-1-0-9.apk` in the repository root and
import it into `.shs-library`. That guide also lists episode-specific inputs
and the optional `extract/assets/Assets/The_New_Girl.exp` fixture. The tests do
not search the desktop app's application-data directory. These local paths
are ignored by Git and never packaged. Do not commit originals as fixtures.

Corpus tools accept user-supplied paths:

```sh
uv run --locked python tools/audit_format.py /path/to/Episodes
uv run --locked python tools/audit_vm.py /path/to/Episodes
uv run --locked python tools/audit_runtime.py --library /path/to/library
uv run --locked python tools/audit_ui_assets.py /path/to/game.apk
```

Treat generated JSON as local evidence; traces can include original dialogue
and player data. The specifications distinguish native contracts, historical
corpus observations and unverified behavior. A passing synthetic test suite
does not establish complete episode playback or pixel/timing equivalence.

## Migration from the research project

| Research project | Standalone project |
| --- | --- |
| `src/exp_file` Python package | `src/shs_runtime` |
| `exp-file` command | `shs-tool` |
| `shs` desktop launcher | `shs` |
| Heuristic AST/Ren'Py conversion | Retained only in the old research project |
| Legacy extraction used by `trace` | Strict `content.ExpArchive` reader |

Save JSON and library schemas do not contain Python module paths; their
versions, resource IDs and content hashes remain unchanged. The application
still uses the `SHS Runtime` user-data folder and existing launcher preference.
Use **Open Library** to select a prior `.shs-library` in another directory.
There is no need to move or reimport that content.

### Migration verification, 2026-09-13

The standalone project was installed into a fresh environment with its locked
dependencies on macOS arm64, using Python 3.14.7. The suite reported 142 tests:
114 passed and 28 optional original-content checks skipped. Additional checks
opened the existing 272-episode research library, loaded and round-tripped its
seven saved sessions, and rendered its menu, 28 episode groups and a saved
episode using the renamed package. Original manifest, preferences and save
hashes were unchanged.

The macOS app built from the standalone source. SDL dummy-driver smoke checks
covered both empty-library setup and an existing-library menu from an unrelated
working directory. Source and wheel archives were inspected for the intended
package, required docs/tools/tests, and exclusion of original game files and
legacy conversion code. These migration checks do not add Windows/Linux or
full original-game visual-equivalence coverage.
