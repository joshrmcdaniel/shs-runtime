# Project provenance and evidence

SHS Runtime was separated from the `exp-decoder-python` research project on
2026-09-13. It retains the compatible engine, original-format readers, authored
tests, build tools and specifications developed there. The inherited MIT
license and Josh Mcdaniel's copyright notice remain in [LICENSE](../LICENSE).

The standalone package is named `shs_runtime`, with `shs` and `shs-tool` entry
points. The original checkout retains the older heuristic AST parser, Ren'Py
exporter, conversion attempts, local assets and raw native research output.
This project has no dependency on that directory or its Python environment.

This is a compatible engine with a KiWi bytecode interpreter. It does not
recompile or execute the original ARM game executable. The fidelity target is
the reported identical original iOS/Android interface; Android 1.0.9 provides
the available native code and asset reference. Unknown platform differences
remain explicit rather than being assumed equivalent.

## Evidence notes

Native function addresses in the specifications refer to `libshs09.so` with
SHA-256:

```text
b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b
```

Names such as `native-kiwi-vm.c`, `native-exp-loader.c` and
`new-girl-start-trace.json` identify private evidence snapshots in the original
research checkout. The raw decompilations and generated traces are deliberately
not copied into this project. References to them are descriptive, not links
to required source files. The specifications preserve the native addresses,
schemas, observations, known ambiguities and implementation limits needed to
continue the work using a user-supplied binary.

Historical corpus counts describe the inputs and coverage of particular
research runs. They are not release guarantees or evidence that all episodes
finish successfully. The audit tools can generate new reports from a player's
own inputs. Keep those reports local because they may contain original game
text and machine-specific paths.

The project contains no original APK, episode archive, native executable,
image/font/audio asset, original screenshot, imported library or player save.
Users supply those inputs separately as described in [DISTRIBUTION.md](DISTRIBUTION.md).
