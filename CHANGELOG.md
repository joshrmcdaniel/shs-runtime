# Changelog

User-visible changes are recorded here. Changes awaiting a versioned release
are listed under Unreleased.

## Unreleased

### Fixed

- Relationship indicators now read the correct NPC property, so script changes
  update the icons and count, including Adam's four skulls in Football Star.
- Implemented service 39's dialogue panel cleanup, fixing the Football Star
  stop at scene 25013, PC 13. Saves paused there resume from their existing state.
- Fixed Football Star's word-grid tutorial initialization by matching the
  native word-list parser and accepting instruction pages with no targets and
  unused failure links. Playable-grid validation remains enforced.
- Restored the word-grid UI's original bitmap fonts, tutorial panels, portrait
  placement, time/score display, cloud borders and word prompts. Added native
  banner and panel motion, outgoing tile faces, and corrected hint/trace art.
  Save version 7 retains these animations and reads earlier saves.
- Restored Strength Up and other service-88 notifications with the original
  lettering, portrait-relative placement, rising letters and fade. Corrected
  their lifetime and dismissal on dialogue taps. The fix applies across
  episodes, and existing saves retain their remaining notice time.

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
