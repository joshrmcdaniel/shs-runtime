# SHS Runtime

An experimental compatible engine for **Surviving High School**, aiming to
reproduce the original interface and gameplay. It executes the original KiWi
scripts and reads graphics, fonts, audio and episode data from files supplied
by each player.

You need your own **SHS Android 1.0.9 APK** and any additional **EXP episodes**
you want to play. The importer reads those files locally. Game content is not
included in this project and is not downloaded by it.

## Build your own app

Install Git and uv, clone this project, then run from the project's directory:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

No game files are needed during the build. Python 3.10 or newer is required;
uv prepares the local environment and installs the locked dependencies.

| Platform | App to open |
| --- | --- |
| macOS | `dist/desktop/SHS Runtime.app` |
| Windows | `dist/desktop/SHS Runtime/SHS Runtime.exe` |
| Linux | `dist/desktop/SHS Runtime/SHS Runtime` |

Build on the operating system where you will play. Keep the whole app or
executable directory together: it includes Python and its dependencies.
macOS on Apple Silicon has been tested; Windows and Linux need validation.

You can also run directly from source:

```sh
uv run --locked --extra desktop shs
```

## Add your game files

1. Launch the app and choose your APK on the setup screen.
2. Add EXP files or an episode folder through Options, or drag them onto the
   menu. The APK's bundled episodes, including Football Star, are imported
   automatically.
3. Select an episode in Play/Resume. Imported episodes and progress persist
   when you close the app.

If your episode folder includes the original `shs_options.sav`, its category
catalog supplies the original season/story groups. It can also be added
separately. Without that optional file, unknown groups use numeric pack names.

Existing libraries from `exp-decoder-python` still work: choose **Open Library**
and select the existing library directory. It can stay outside this project.
The content IDs, library schema, save schema and per-user application-data
locations are unchanged. See [runtime setup](docs/RUNTIME.md) for paths,
controls, formats and command-line import.

## Current state

The runtime implements the main menu, persistent episode library, grouped
episode browser, dialogue animation, portrait masks, choices, character
selection, relationship indicators, loading screens, word/grid/football mini
games and save/load. F5 saves, F9 loads, and returning to the menu creates an
automatic checkpoint. Tap once to reveal dialogue, then again to advance it.

The New Girl opening and Football Star opening through its first football
game have been exercised. Complete episode playback and full 1:1 visual/timing
equivalence are still being verified. Unsupported services stop explicitly
with their scene, service and program counter. Current limits are recorded in
[RUNTIME.md](docs/RUNTIME.md) and [ENGINE_ABI.md](docs/ENGINE_ABI.md).

## Specifications and development

- [EXP format](docs/SCHEMA.md): container, index, compression, metadata and payloads.
- [KiWi VM](docs/VM_SPEC.md): bytecode, all core opcodes, memory, calls and yields.
- [Engine services](docs/ENGINE_ABI.md): native service contracts and coverage.
- [UI assets](docs/UI_ASSETS.md) and [UI fidelity](docs/UI_FIDELITY.md).
- [Main menu](docs/MAIN_MENU.md) and [episode catalog](docs/EPISODE_CATALOG.md).
- [Mini games](docs/MINIGAMES.md) and [story services](docs/STORY_SERVICES.md).
- [Development and tests](docs/DEVELOPMENT.md), [distribution](docs/DISTRIBUTION.md)
  and [project provenance](docs/PROVENANCE.md).

```sh
uv run --locked --extra desktop python -m unittest discover -s tests
uv run --locked shs-tool --help
```

