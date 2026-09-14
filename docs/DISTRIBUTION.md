# Source distribution and local builds

SHS Runtime provides the compatible engine, KiWi interpreter, local asset
importer, authored specifications, tests and build tools. Each player supplies
the original Android 1.0.9 APK and additional episode EXP files. The original
ARM executable is inspected only to identify the supported APK profile; it is
not executed by the runtime.

## Player workflow

After cloning the project, run from its root directory:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

Open `dist/desktop/SHS Runtime.app` on macOS. Windows and Linux executables
are inside `dist/desktop/SHS Runtime/`; keep that complete directory together.
Build on the target operating system. macOS on Apple Silicon has been tested;
Windows and Linux still need validation.

The build bundles Python and the runtime dependencies. No APK, EXPs, Ghidra,
Ren'Py SDK, extracted resources or old checkout are required to build it.
On first launch, choose your APK and add episode files through the menu.
Extraction happens locally; the application has no game download service.

To run from source instead:

```sh
uv run --locked --extra desktop shs
```

Libraries and saves stay in the user's application-data directory or another
folder they choose. Existing libraries from the research project can be opened
through **Open Library**. Building or updating the engine does not require
copying game content into this source directory. See [MAIN_MENU.md](MAIN_MENU.md)
for library locations and [RUNTIME.md](RUNTIME.md) for current compatibility.

## Public project contents

This standalone directory was assembled from authored source and documents.
It includes no Git history from the research project. Git initialization,
remotes, commits and publication are left to the project owner.

Keep APKs, EXPs, extracted images/audio/fonts/scripts, original screenshots,
native decompilations, generated games, runtime libraries and player saves
outside the public tree. Optional original-content tests read local inputs
and skip when those inputs are absent; ordinary tests use synthetic fixtures.

- `.gitignore` excludes known local game/research paths and generated output
  from normal Git staging. It does not exclude already tracked files.
- `MANIFEST.in` explicitly selects authored source, tests, tools and docs for
  source packages. Setuptools limits Python packages to `src/shs_runtime`.
- `tools/build_desktop.py` bundles the runtime and its dependencies. `LICENSE`
  is the only repository file explicitly collected as executable data.

Research commands can produce traces containing game text and local paths.
Their JSON outputs belong in ignored local directories, not in the published
source. The format and VM specifications retain evidence addresses and
historical verification summaries. See [PROVENANCE.md](PROVENANCE.md) for how
to interpret references to private evidence snapshots.
