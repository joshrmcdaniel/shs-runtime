# Compatible runtime and user content

Revision: 2026-09-13. This is an experimental implementation of the SHS engine.
It executes original KiWi instructions and reuses original assets. It currently
plays the opening of **The New Girl**, including real branching choices and its
first mini game, and implements timed words, word/picture grids and football; it
does not yet play complete episodes.

## Fidelity target and implementation order

The required destination is a **1:1 game experience**, including behavior and
presentation. The existing desktop UI is a temporary playback/debugging frontend.
Its remaining prototype layouts, simplified music playback, and convenient desktop
controls do not define the final design. Dialogue now uses the original APK
layout, fonts, borders and masked portrait frames, with native left/right
placement, progressive text, animated portrait/name transitions and session-owned
pagination. Ordinary choices use a reconstruction
of the supplied original screenshots: one translucent bordered panel, a circular
portrait, the original fonts, divided rows and the gear/footer. Remaining
placement/timing differences are listed in [UI_FIDELITY.md](UI_FIDELITY.md#ordinary-choice-panels).
Mini games reuse the original APK art with recovered input/scoring contracts;
their remaining presentation differences are in [MINIGAMES.md](MINIGAMES.md).
Other screens retain prototype layouts.

The user reports that the iOS and Android interfaces were identical. The
available **Android 1.0.9 executable and APK assets** are therefore the working
reference for reconstructing the shared original interface. Native layout
calculations and shipped glyph/art data take priority over estimates from the
prototype. Newly discovered platform differences must remain explicit; shared
appearance does not establish identical engine internals or platform services.
The current concrete asset/code evidence is in [UI_FIDELITY.md](UI_FIDELITY.md).

Implement fidelity in this order:

| Work | When / reason |
| --- | --- |
| Original coordinate system, asset scale, font metrics, text layout and pagination | Establish early; these determine screen geometry, option placement, and input regions |
| Panel creation/destruction, script-visible panel side effects, input acceptance, animation completion and timers | Model with each engine feature; these affect execution and cannot be recovered by changing colors or textures |
| Minigame rules, timing, random state, input/result mapping | Recover together with the minigame's UI; a visually similar screen can otherwise produce different outcomes |
| Persistent panel/timing state and ordered audio requests | Preserve in the engine/session model as understood; saving only the current visible asset IDs is insufficient for full fidelity |
| Final artwork composition, borders, colors, and small spacing adjustments | Refine after the relevant behavior and layout contracts are stable |

The VM, resource layer, and frontend are already separate. Visual changes should
reuse the EXP decoder and VM, but the current host/presentation state is still
incomplete. Adding native panel, animation, audio, and random state can require
new save fields and explicit save-version migrations. The present save schema
must not prevent those corrections.

Use an original dialogue/choice sequence as an early reference before expanding
the UI. Compare the same inputs against the selected release: VM requests and
game state for behavior, screenshots for stable layouts, and recordings or
frame traces for transitions, sound, and timing. Extend those comparisons to
each recovered minigame. Automated tests of the reimplementation establish its
own consistency; they do not alone establish equivalence to the original.

This permits incremental progress on the missing services while avoiding a
large final rewrite of behavior that was initially treated as styling. All
known approximations remain explicit until their native contract is recovered
and the corresponding comparison passes.

## Distribution model

Each player supplies their own **SHS Android 1.0.9 APK** and any additional
**episode EXP files**. The APK provides the base resource bank, audio, and
three bundled episodes. Additional episode files remain necessary for their
respective stories. There are no game downloads or dependencies on this
repository's extracted assets, Ren'Py projects, Ghidra installation, or original
directory layout.

The reusable program ships separately from that content. This is the same
user-supplied-content model discussed for game recompilation projects; this
implementation is a **compatible engine with a KiWi interpreter**, rather
than a static recompilation of the ARM executable. APK native code is used
only to identify the supported profile; it is never executed.

`MANIFEST.in` explicitly selects runtime source and authored documentation for
the source distribution. Setuptools package discovery is restricted to
`src/shs_runtime`. Original APKs/EXPs, extracted art/audio, decompiled native C,
generated Ren'Py games, and saved progress are excluded from Python packages
and executable builds. Players can clone the engine's source and build their
own executable before supplying any game content. See
[DISTRIBUTION.md](DISTRIBUTION.md) for that workflow and the separate Git
publishing boundary. The standalone project contains authored files and no
Git history or native decompilations from the research checkout. Libraries
created under custom directory names must likewise remain local.

## Install and play

From a source checkout:

```sh
uv run --locked --extra desktop shs
```

`shs` (or `shs-tool play` without `--episode`) opens the main menu and, on first
launch, a file picker for the player's APK. Options accepts additional episode
files or folders. Drag-and-drop also works, including multiple files together.
The original menu art/fonts come from the APK. See [MAIN_MENU.md](MAIN_MENU.md)
for recovered native state/asset contracts, desktop adaptations and executable
build instructions.

Command-line imports and direct episode launch remain supported:

```sh
uv run --locked shs-tool import --apk /path/to/game.apk --episodes /path/to/Episodes --library /path/to/my-shs-library
uv run --locked shs-tool list --library /path/to/my-shs-library
uv run --locked --extra desktop shs-tool play --library /path/to/my-shs-library --episode "The_New_Girl.exp"
```

Without uv, install with `python -m pip install -e '.[desktop]'`, then use
`shs-tool` from that environment. Decoder/headless tools do not require pygame.

`--episodes` accepts multiple files or directories and recursively finds EXP
files, including uppercase `.EXP`. It is optional when using only the episodes
inside the supplied APK. Import creates a **new** library directory; it refuses
to overwrite an existing library. Add more episodes through the app's Options
screen; the batch is validated before updating the manifest. Saves can be copied
between libraries with identical content hashes. Imports preserve supplied files.

Import/list default to `.shs-library` in the current working directory. The
player uses an existing local library in a source checkout, otherwise per-user
application data. A frozen executable always uses per-user application data;
it never stores content beside the executable. `--library` overrides the path.
`--episode` accepts an exact title, filename, or unique hash prefix printed by
`list`. Starting with `play --episode` begins a fresh session. To resume the
newer automatic/manual checkpoint:

```sh
uv run --locked shs-tool play --library /path/to/my-shs-library --episode "The_New_Girl.exp" --resume
```

`--load /path/to/progress.shs-save.json` loads a specific save instead.
`--no-audio` disables playback. These are runtime JSON saves; original game
saves are not supported.

| Input | Action |
| --- | --- |
| Checkmark, tap dialogue, Enter, or Space | Finish an unfinished text reveal; once complete, show the next page or acknowledge the VM after the last page |
| Continue button / Enter / Space on a title screen | Acknowledge that presentation |
| Click an option or press 1–9 | Submit that choice to the VM |
| Click a word or press 1–4 in timed words | Score the selected word and deal new options |
| Hold and drag across grid cells | Trace a word or picture sequence, including diagonal steps; no repeated cell |
| Click a football target or press 1–9 | Commit that play; targets change over time |
| Tap football help / Enter / Space | Continue after its native reading delay |
| Gear on dialogue, choice or mini-game screens | Open Resume/Save/Load/Main Menu; active game time pauses |
| Type, Backspace, Enter | Edit and submit a text input |
| Save button / F5 | Replace the current episode's local save slot |
| Load button / F9 | Restore that slot |
| Wheel, arrow keys, Page Up/Down | Scroll long option lists and other non-dialogue screens |
| Escape | Open/close the pause menu during play; go back within application menus |
| Main Menu / Close window | Save a separate automatic checkpoint and return to the menu / exit |

## Content library contract, version 1

```text
library/
  library.json
  content/<APK SHA-256>.apk
  content/<EXP SHA-256>.exp       # external episodes only
  saves/<EXP SHA-256>.shs-save.json
```

The manifest has `format: "shs-content-library"`, `version: 1`, and
`profile: "shs-android-1.0.9"`. `apk` contains `file`, `sha256`, and
`native_sha256`. Each `episodes` entry contains:

| Field | Type / meaning |
| --- | --- |
| `id`, `sha256` | Identical lowercase 64-digit SHA-256 of the complete EXP bytes |
| `name` | Original basename, for display/selection |
| `pack_id`, `episode_id` | Unsigned metadata words |
| `titles` | Five UTF-8 localized metadata strings, in archive order |
| `scripts` | Sorted exact resource IDs containing KiWi programs |
| `file` **or** `apk_member` | Copied EXP path or member inside the copied APK |

Duplicate EXP bytes produce one entry, even when supplied under different
names or also present inside the APK. Metadata IDs alone are not unique content
identities. All filesystem paths in the manifest are relative, content-derived
paths, so the entire library can be moved to another directory or computer.

The optional manifest field `episode_catalog` retains original English category
metadata imported from a user's `shs_options.sav`. It supplies season and story
group headers without changing EXP identities or saves. Folder/EXP imports
discover this optional sidecar; users can also add it through the episode
picker. The native envelope, normalized metadata schema, matching and fallback
rules are in [EPISODE_CATALOG.md](EPISODE_CATALOG.md).

Import validates a private copy of the APK, decodes all imported EXP payloads,
and parses their KiWi programs before publishing the library by directory
rename. A failed import leaves no partially initialized destination. ZIP paths
are never extracted. Import checks duplicate ZIP member names and rejects an
unknown native profile. The supported member is `lib/armeabi/libshs09.so`, with
SHA-256:

```text
b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b
```

The APK file hash is checked when opening the library; the selected EXP hash
is checked when opening its episode. The native-library hash identifies the
engine profile, whereas the **complete APK and EXP hashes** identify save
compatibility. A differently repacked APK with the same native binary may
import but has a different save identity.

The runtime's strict EXP reader follows [SCHEMA.md](SCHEMA.md): BE outer
fields, the LE LZMA wrapper, aliases, and five UTF-8 titles. It rejects partial
overlap, duplicate IDs, unknown flag bits, inconsistent sizes, unsupported
compression properties, and oversized records/members (64 MiB). These checks
are a supported-input policy; the native reader is less defensive and, for
example, ignores compression flag bits other than bit 0. Native grouped
fallback and EXPD variants remain unsupported.

## Resource and execution boundaries

| Layer | Responsibility |
| --- | --- |
| `content.py` | Import, profile/content identity, EXP reader, resource banks |
| `decode/bytecode.py` | Lossless KiWi schema decoder |
| `vm.py` | Signed-word execution, memory, calls, branches, suspension |
| `engine.py` | Native host services and persistent game/panel state |
| `runtime.py` | Input callbacks, scene scheduling, timers, save/load |
| `fonts.py` | Original descriptor records, native text metrics, wrapping, color controls |
| `ui_assets.py` | Native layout records, ARGB/alpha image packs, transforms and masks |
| `atlas.py` | ABGR sprite atlases, signed composites and binary glyph-font records |
| `minigames.py`, `word_grid.py`, `football.py` | Game rules, random streams, input phases, scoring and clocks |
| `dialogue.py` | Native dialogue geometry, name placement and page layout |
| `desktop_text.py` | Original atlas drawing for dialogue; font/layout/glyph caches |
| `desktop_dialogue.py` | Original dialogue artwork and portrait composition |
| `desktop.py` | pygame input, presentation, images, and basic audio |
| `menu.py`, `desktop_menu.py` | Native menu geometry, string/glyph resources, menu UI, local preferences/checkpoints |
| `application.py` | Setup/import, menu navigation, session lifecycle, worker/event loop and exit |

The original script chooses the next instruction. A button submits an option
index; the runtime performs the recovered callback, and the VM executes the
resulting branch. A renderer does not select scene links or interpret nearby
numbers as dialogue.

Native image-bank selection (`FUN_00082bc0`) uses the APK bank for resource IDs
below 26000 and the selected EXP bank for IDs at least 26000. APK numeric files
live directly under `assets/Assets/`; six native IDs have a `.mp3` suffix,
including image pack 16. The audio subdirectories have explicit
numeric filenames. Font/image/animation atlas filenames in other subdirectories
are separate namespaces, so `images/1.png` never replaces global resource 1.
An absent episode resource does not silently fall back to an unrelated APK ID.
Named UI resources are read explicitly with `ContentLibrary.read_ui_asset()`.
Font atlases are read directly from the imported APK, including `.dat` files
that contain PNG data. Neither original font tables nor images ship with the
runtime; no system-font installation is needed for the recovered dialogue path.

Script loading follows a different path: the selected episode's exact script
IDs take priority, including its scripts in the 25000 range. Playback starts at
25001. Service 10 appends a scheduled script; after HALT the runtime loads the
last scheduled script. Registers and complete stack backing survive that load,
while data and PC/SP/FP reset according to the core VM contract.

## Runtime save schema, version 7

This is a new format for the reimplementation. No pickle, object deserialization,
or original executable code is used. JSON fields are:

| Field | Contract |
| --- | --- |
| `format`, `version` | `"shs-runtime-save"`, `7` |
| `content` | `profile`, `apk_sha256`, `episode_sha256`; must exactly match loaded content |
| `scene` | Unsigned current script resource ID |
| `script_sha256` | Hash of the losslessly encoded current program |
| `vm` | Full mutable machine state, defined below |
| `engine` | All current `EngineState` dataclass fields, including panel, dialogue animation, choice builder, random streams and any active mini game |
| `pending` | Null, or `{name, details}` for the suspended screen/service |
| `remaining_ms` | Null for no timer; otherwise the remaining active choice time in milliseconds |
| `scene_loads` | Nonnegative number of scheduled script loads |

The `vm` object contains `pc`, `sp`, `fp`, `a`, `b`, `result`, `data`, `stack`,
`pending`, `steps_executed`, `opcode_counts`, and `recent_pcs`.

- Memory/register words are signed 16-bit integers or JSON null for
  uninitialized storage. Null must not be changed to zero on load.
- `stack` contains **all allocated cells**, including cells above SP. Popped
  values remain addressable by native scripts. `data` includes the mutable
  initialized words and gap cells, not just changes to the original script.
- `vm.pending` is null or `{kind, pc, byte_offset, yield_id, args}`. Its PC is the
  issuing instruction; `vm.pc` is already advanced for a yield or pause and
  remains on the HALT instruction for a halt. Pending argument words remain
  in the stack until the callback completes. Service 91(0) is an application
  gate after an already completed call: its loading screen has `vm.pending=null`.
- `opcode_counts` and numeric engine map keys use decimal strings as JSON
  object keys. They are restored to integer keys in memory.
- `engine` includes numeric/string variables, names and art variants, expression
  bytes, all 11 dynamic string slots, 10 optional result words, UI defaults,
  scheduled `(script_id, flag)` records, panel presentation, audio requests,
  last input, and any choice under construction. A text-input draft is retained
  in its pending screen details when saving from the desktop.

The panel additionally stores `presentation_mode` (native modes 1–4, or 0
before setup), `theme`, and `emphasis_theme` (last ordinary theme-1/2 backtick
palette). `mode` is still the separate script text-decoration prefix.
A pending dialogue includes the requested `character_id`, `visible_character_id`,
visible `speaker`, `expression`, raw/displayed text, those mode/palette fields,
and `page_start` / `page_end`, as Latin-1 source-byte offsets. The VM stays
suspended while these offsets advance. Page layout is derived from the same
user-supplied APK; saved page extents are checked on load.

Version-1 saves are migrated without executing the pending VM instruction or
replaying choices. Pending dialogue is reconstructed from its raw text and
configured character IDs, fixing old visible narrator names and thought text.
It starts on page zero because version 1 stored no page position. Historical
font state absent from version 1 starts with the initial palette, then applies
the current dialogue theme. Unknown save versions are rejected.

Version 3 adds `random48`, `random`, `word_game`, `football`, `football_scores`,
`word_grid`, `grid_tutorials_seen`, `sound_ids`, and queued/active dialogue notice
state. Game fields include generated choices/boards/targets, score, consumed
starts, pointer selection, phases, timers and sound requests. Both random
generator states are integers. Games are restored without consuming randomness;
their typed fields and correspondence to the pending VM request are validated.
See [MINIGAMES.md](MINIGAMES.md#7-saves-verification-and-remaining-fidelity-work).
Version 1/2 saves receive defaults for these fields. If their retained stop is
service 71, 94 or 96, the game is initialized from that original frame; missing
historical random state cannot be reconstructed.

Service-88 notices derive their letter motion from the existing remaining
`notice_ms` countdown, independently of the dialogue reveal clock. Its native
upper bound is `165*(len(notice)+1)+300` for nonempty text, zero otherwise.
Older notice saves retain their remaining time and VM state. No fields were
added for this rendering correction. See the
[notification contract](STORY_SERVICES.md#dialogue-notifications-service-88).

Version 4 adds `dialogue_animation`: the current and outgoing portrait identities,
speaker/page transition flags, active elapsed time, source-index reveal counter,
completion flag and pending fast-completion state. The field is required on a
pending dialogue, can survive a VM pause, and is null on other presented screen
types. See the field schema and native timing evidence in
[UI_FIDELITY.md](UI_FIDELITY.md#dialogue-transitions-and-reveal-scheduler).
Version-1/2/3 dialogue saves migrate with the current page fully revealed and
its entrance settled, preserving their previous immediately visible behavior.
They retain the saved VM frame and, for version 2/3, the page offset.

Version 5 adds `character_picker`, `scene_badge`, `next_dialogue_wobble`, and dialogue animation `wobble_direction`. These hold copied character IDs, their index permutation, per-portrait 50 ms motions, the 200 ms scene-label entrance, and the next dialogue rotation. The complete typed field schema is in [STORY_SERVICES.md](STORY_SERVICES.md#save-schema-additions-version-5). Older saves receive null/false/zero defaults; a retained unsupported service-78 frame upgrades to a working selector without replaying earlier choices. Existing dialogue checkpoints retain their progress.

For portrait selection, click and release a portrait, then click the checkmark. Keys 1–5 select the original portrait index; Enter/Space confirms. `Session.answer(index)` selects without completing, and `Session.answer()` confirms. Animation freezes while paused or unfocused.

Version 6 adds the service-91 loading gate and relationship indicator animation
state. A loading screen continues automatically only when active time exceeds
3000 ms; a click cannot dismiss it. NPC icon/count changes write the original
cache keys, play the native sound, and add their original dialogue delay.
Older unsupported service-91 saves enter the recovered screen; old dialogue
checkpoints acquire settled icons without losing reveal/page progress. See
[STORY_SERVICES.md](STORY_SERVICES.md#save-schema-additions-version-6) for the
fields, validation and migration rules.

Version 7 adds `visual_ms`, `board_entry_ms`, `banner` and `transition` to the word-grid state.
They preserve active decorative time, the banner's entrance/hold clock, and
outgoing letters during board transitions. The renderer uses the original
atlas fonts and instruction panel geometry without mutating the VM or game.
Earlier grid saves keep their exact board, score, selection and random state;
missing decorative history starts at zero/null. See
[GRID_UI.md](GRID_UI.md#saved-presentation-and-verification) for the typed schema.

A save retained at unsupported service 39 now completes the recovered panel
close through its validated VM frame and follows the saved script queue to
the next stop. This also applies to version-6 saves; no schema fields change.
Earlier choices and random draws are not replayed. See
[STORY_SERVICES.md](STORY_SERVICES.md#dialogue-panel-close-service-39).

Loading checks content identity, program identity, machine extents, field
types, and correspondence between the pending request, saved instruction, and
argument frame. It restores the suspended screen directly. It does not replay
prior script input or reapply choice side effects. Saving uses a temporary file
and atomic replacement, with one slot per episode by default.

Timers count active foreground time. Saving preserves the remaining interval;
time spent with the application closed or unfocused does not consume it. Audio
position is not serialized; loading restarts the requested music track.
Implemented dialogue/mini-game animation clocks and both modeled random streams
are serialized. Other native animation and panel-lifecycle state remains partial;
newly modeled fields will require explicit save migrations.

## Verified playback and remaining work

With the supplied local APK, the runtime executes 25001 initialization, loads
25002, and reaches service 8's opening presentation after 2,561 instructions.
After acknowledging 35 title/dialogue screens it reaches service 1 at PC 316.
Submitting options 0 and 1 reaches different original dialogue instructions at
PCs 336 and 352. Save/load at that choice preserves both possible continuations.
Continuing reaches **service 71 at PC 92**, still in scene 25002. This timed
word game is now playable, and scores 0 and 10 produce different actual script
branches. Service 88's post-game notification now continues into dialogue.
An all-first-choice route with ten positive word selections reaches service 91
at PC 60 in scene 25004; its loading gate is now implemented. Separate local tests
exercise the original driving-grid frame in script 25003 and the football
frame in **Big Man On Campus** without adding production script skips.

The full local import audit consumed 274 archive paths (271 external paths and
three APK members), deduplicated them to **271 distinct episodes**, and parsed
**974 distinct-episode script records**, with no import or startup exception.
Initial stops were 58 title presentations, 53 dialogue screens, 159 unsupported
service-99 calls, and one unsupported service-89 call. See
`runtime-import-audit.json`. These counts describe
initialization only, not complete episode support.
The startup audit was repeated after adding dialogue layout and pagination:
`runtime-panel-audit.json` has the same counts and
zero failures across all 271 episodes and 974 script records.

Reproduce the audit from the source checkout (the temporary imported copy is
removed afterward):

```sh
uv run --locked python tools/audit_runtime.py --apk surviving-high-school-1-0-9.apk --episodes Episodes > docs/runtime-import-audit.json
```

Use `--library /path/to/library` instead to audit an existing import.

The authored unit tests cover hostile/truncated archives, compressed aliases,
relocatable imports, wrong profiles/content, actual branch execution, scene
loads, complete saved stack/data, timers, custom choice values, text callbacks,
unsupported-service suspension, and desktop keyboard/mouse/save/load behavior.
Text tests cover the native descriptor quirks, wrapping independently of
kerning, color controls, original atlas dimensions, glyph alpha, and clipping.
Optional tests exercise the local New Girl content without packaging it as a
fixture. New checks cover image-pack transforms, mask alignment, signed layout
coordinates, configured narrator IDs, version-1 migration and saved page turns.
Choice checks cover native font/skin composition, neutral portraits, disabled
rows, long-list hit testing, resized selection, custom result mappings and menu
timer suspension. Rendering never answers a pending choice.
Dialogue checks cover delayed/progressive reveal, fast-completion taps without
VM acknowledgement, speaker swaps on either side, repeated speakers, page
delays, clock partitioning, old-save migration and mid-transition save/load.
Local rendering checks confirm intermediate portrait frames and freeze clocks
on menu pause/focus loss. A macOS Cocoa smoke check rendered 401 dialogue frames
and restored a partially revealed frame with identical pixels.
Mini-game checks cover native random vectors, word scoring, grid tutorials and
path rules, football drives and overtime, callbacks, saved random replay,
malformed state and original sprites. Desktop tests exercise each game using
resized pointer coordinates, menu pause and focus loss. These checks do not
establish full equivalence to a running original game.
Run `uv run --locked python -m unittest discover -s tests`.

Remaining compatibility work includes other scene/state services, remaining
mini-game presentation and global random-state
lifetimes, linked KiWi, native
saves, grouped resources, remaining texture/composite animation formats, and
iOS/Android differences. Dialogue uses the original fonts, layout bank, box
artwork, masked portrait placement and paging. Narration hides the configured
character's name and portrait; thought prefixes add parentheses. Ordinary
choices use the supplied screenshot layout and APK artwork; title/text-input
screens retain prototype fonts/layouts. Dialogue portraits scale in/out and
names fade while text reveals; backgrounds remain static, with basic music/SFX
playback. NPC relationship icons now use original assets, cache writes, sounds,
gains/losses and dialogue delays. Cross-object kerning, name-fitting exceptions,
scene transitions and native global input locks remain incomplete; see
[UI_FIDELITY.md](UI_FIDELITY.md). Native panel lifecycle and Android promotional
branches, music repeat/fades, and all channel behavior are not fully reproduced.
Text entry currently accepts up to 20 Latin-1 characters; that limit is a
prototype constraint, not a fully recovered input-widget specification.

The exploratory Ren'Py exporter remains in the original research checkout
and is not included in this standalone runtime.

## Built-in Football Star extraction

The importer extracts the 22 loose APK scripts into a deterministic local EXP with native IDs 25001–25021 and 25023. Its five titles come from string-bank 13, entries 193–197; pack/episode IDs are 0/0. Shared art/audio remain in the APK bank. Startup upgrades existing libraries atomically and preserves their episodes, preferences and saves. See [MAIN_MENU.md](MAIN_MENU.md#built-in-story-extraction).

The opening has been exercised through character creation, the first classes,
service 91 in scene 25006 at PC 1245, and the following football mini game at
PC 1270. Both halves complete through ordinary tap/tick input and the original
script returns to Howard's dialogue. This required services 0, 24, 25, 27, 28,
50, 51, 78, 82, 89, 90, 91 and 99 alongside the existing game handlers.
Extraction includes the whole story; this check does not establish full-story
playback. Earlier 271-episode audit counts above are historical and predate
these newly supported services.
