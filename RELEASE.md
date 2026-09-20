# Unreleased

## Fixed

- Fixed the imported New Girl episode's portrait-mask error. Larger portrait
  variants now render at half size before masking, preserving aspect ratio,
  transparency and orientation. Existing libraries need no content reimport.
- Timed choices now show the original circular countdown and timer panel.
  The timer stays visible when long lists scroll, freezes while paused or
  unfocused, and restores from saved time. Corrected expiry to occur just after
  zero, preserving the script's timeout selection and custom return values.
- Fixed the APK-bundled New Girl episode stopping at `yield 91 at pc 60:
  expected 1 arguments, got 0`. Loading now accepts both bundled and imported
  episode calls, preserving their native timer and VM frames through save/load.
  Existing libraries need no content reimport.
- Restored the name-entry screen's original panels, bitmap fonts, layout,
  cursor and invalid-input alert. Typing now follows the native capitalization,
  alphanumeric, 16-character and width rules, with Return to confirm. Drafts
  survive save/load, and rejected input leaves the pending script unchanged.
