# v0.1.0

SHS Runtime is an experimental compatible engine for Surviving High School.

Download the archive matching your system, extract it, and keep the complete
app or executable folder together. Python is included; no development tools
are needed to play a downloaded build.

- **macos-arm64:** Apple Silicon Macs.
- **macos-x64:** Intel Macs.
- **windows-x64:** 64-bit Intel/AMD Windows PCs.
- **linux-x64:** 64-bit Intel/AMD Linux PCs (built on Ubuntu 22.04).

On first launch, supply your own **SHS Android 1.0.9 APK**, then add your
**EXP episode files** through Options. Existing libraries can be selected
with **Open Library**. These downloads contain the engine and its dependencies;
game assets are imported locally from the files you provide.

The `.sha256` files contain checksums for their corresponding archives.
macOS builds use ad-hoc signing and are not notarized. Windows builds are
unsigned. Your operating system may require approval before the first launch.

Complete episode playback and full original-game fidelity remain in progress.
See the repository's runtime and engine-service documentation for current
support and known limits.
