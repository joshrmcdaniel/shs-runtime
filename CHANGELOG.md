# Changelog

User-visible changes are recorded here. Changes awaiting a versioned release
are listed under Unreleased.

## Unreleased

### Fixed

- Relationship indicators now read the correct NPC property, so script changes
  update the icons and count, including Adam's four skulls in Football Star.

## v0.1.0

### Added

- Compatible KiWi engine that executes original scripts and imports resources
  locally from a player-supplied Android 1.0.9 APK and EXP episodes.
- Desktop launcher and main menu with persistent episode libraries, catalog
  grouping, manual saves and automatic checkpoints.
- Dialogue animation, portrait masks, choices, character selection,
  relationship indicators, and word, grid and football mini games.
- EXP, VM, engine-service and UI specifications documenting recovered behavior
  and remaining uncertainties.

### Known limitations

- Complete episode playback and full original-game fidelity remain in
  progress. Unsupported services stop explicitly with their pending arguments
  preserved.
- macOS builds use ad-hoc signing and are not notarized; Windows builds are
  unsigned.
