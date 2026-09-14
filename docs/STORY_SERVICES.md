# Portrait selection and built-in story services

Reference: SHS Android 1.0.9, `libshs09.so`, SHA-256
`b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b`.
These are host-service contracts; VM opcodes and EXP resource IDs are separate
namespaces. All assets, text and bytecode come from the player's content.

## Dialogue panel close (service 39)

```text
arguments : none read; any supplied argument words are discarded on completion
target    : current dialogue panel, native UI type 3
result    : 0, immediately; no input callback or additional timer
effect    : retire that panel's presentation state
```

Dispatcher case `0x27` looks up panel 3 through `FUN_0007dff0`, then calls
`FUN_000a7cd0`. That helper sets the byte at panel `+0x0c` to 1. The panel's
virtual slot `+0x30` points to `0x000a63e0`, which reads that byte. Scene update
`FUN_0007feac` checks it and removes the panel through `FUN_0007fd28`, calling
deactivation, cleanup and destruction. This flag is separate from the callback
flag at panel `+0x0d`; service 39 does not suspend the VM for user input.
The ordinary dispatcher completion returns zero and removes the entire pending
argument frame. It does not choose or schedule another script.

The compatible host clears the dialogue panel's background, speaker, text,
portrait and animation state, plus its active/queued notice (service 88 stores
the queued text at panel `+0xf0`). A subsequent panel starts without an outgoing
portrait or stale speaker name. Character definitions, relationship properties
and caches, other numeric/string state, result cells, randomness, audio requests
and scheduled scripts survive. The scene-owned badge and queued wobble survive
as well; services 90 and 89 store those outside the dialogue panel.

Native removal happens in the scene update or the cleanup at script HALT
(`FUN_0007e4c4`). The runtime retires the panel during dispatch, before its next
presented screen. The full native panel stack and ordering of several panel
operations within a single frame remain a fidelity boundary.

Football Star scene 25013 issues service 39 at PC 13, then HALTs at PC 14.
The existing LIFO schedule determines what runs next. Saves retained at the
previously unsupported call are validated and resumed through the handler on
load, then execute normally to the next stop. No prior choices or random draws
are replayed, and save version 6 needs no new fields.

## Portrait selection (service 78)

```text
arguments : [prompt_reference:s16, count:s16, characters_address:s16]
characters: copy of count signed VM words at characters_address
order     : [0, 1, ..., count-1]          # original array indices
result    : order[0], on confirmation only
side effect: UI result cell 0 = result
```

The factory constructs UI type 5 with `FUN_000d2cb8` and passes substituted
prompt text and copied character IDs to `FUN_000d2238`. That function initializes
the five inline index slots at panel `+0x70`. Supported count is 1–5. Unreadable
words and invalid counts fail explicitly, retaining the pending VM call.

`FUN_000d1d78` swaps `order[0]` with the touched slot and swaps its portrait
widget pointer. `FUN_000d1b48` returns the first **index**, not a character ID.
`FUN_000d2008` selects on touch release; touching the central portrait does
nothing. Confirmation is separate, and the initially selected first portrait
can be confirmed immediately. Selection does not mutate VM memory, set the
result cell, or resume execution. Confirmation can occur during a swap.

### Geometry and motion

The native logical display is 320 × 480. `DAT_0025b830` holds these GL centers,
and `DAT_0025b81c` holds scales. Top-origin values are used in the renderer.

| Slot | GL center | Top-origin center | Scale | Opacity |
| --- | --- | --- | --- | --- |
| 0, selected | (160,205) | (160,275) | 1.0 | 255 |
| 1 | (52,239) | (52,241) | 0.6 | 91 |
| 2 | (115,310) | (115,170) | 0.6 | 91 |
| 3 | (206,310) | (206,170) | 0.6 | 91 |
| 4 | (269,239) | (269,241) | 0.6 | 91 |

Hit circles are fixed to these centers, radius `61 * scale`, even while widgets
move. When either swapped widget has no running action, both move to the other's
current position in 50 ms, scaling to 1.0/0.6; opacity is assigned by current
slot as `int(scale*scale*255)`. If both are moving, indices still swap but new
motion is not started. State retains per-character motion, independently of
render frequency. Selection and confirmation request sounds 8013 and 8010.

`FUN_000d2238` reads layout 47 but overrides the root to `(0,120,320,240)`.
`FUN_000d2558` uses the first supplied character's property 651 for its skin.
Portraits each use expression zero, mode 1, common selection frame 43/44,
the original mask 268, and the native 12-row portrait crop. Nonselected portraits
are deliberately faded. There is no invented character name or option text.

The prompt uses the existing `DAT_002ae910` PajamaHip26 node at GL (180,390),
size 300 × 45, nominal height 16, initial gap -16, white modulation. The
checkmark is common frame 41 at GL (240,111). Its release hit regions combine
the native explicit rectangle and transformed sprite rectangle. Footer text
comes from string-bank 13 entry 37. Desktop keys 1–5 select original indices;
Enter/Space confirms. The gear pauses motion; focus loss cancels a pending
pointer gesture. Subpixel rasterization and the native pressed-checkmark tint
remain presentation refinements.

Homecoming Queen, scene 25003, PC 303 passes `(426,5,6262)` with character IDs
`[0,29,30,31,32]`. Tests verify all five original results: art groups 26000,
26005, 26010, 26015 and 26020 are assigned to character 0 by the original script,
then the dialogue at PC 319 runs. A save at the older unsupported stop migrates
without replaying earlier choices.

## Formatting and packed strings (services 0, 24, 25, 28)

Service 0 uses `FUN_0009f5cc(host,0)`:

```text
if a1 >= 0: destination_slot=0; format=t(a1); values=a2...
else:       destination_slot=1-a1; format=t(a2); values=a3...
scratch_slot_10 = ""
scan format left to right:
    %c -> low byte of next word
    %d -> decimal signed 16-bit next word
    %s -> raw t(next word), with no variable substitution
    other bytes -> literal, including unrecognized percent pairs
destination_slot = scratch_slot_10
return 0x7ff5 + destination_slot
```

The format is copied before clearing scratch slot 10. Scratch updates as bytes
are appended, so a `%s` referencing handle 0x7fff observes the partial output.
For example, scratch containing `A%sB` formatted with itself as the `%s` argument
produces `AAB`. There is no printf `%%` escape: unrecognized `%` bytes remain
literal and the following byte is scanned normally. Extra arguments are removed
with the original frame but ignored by formatting; missing required arguments
fail. Destinations are bounded to the eleven known slots (0–10); selector -10
and below are rejected instead of writing past native storage. Width/precision
modifiers are not invented. Service 22 has different scanning behavior and
remains unsupported.

Service 24 compares two raw texts and returns 1 for equality, otherwise 0.
Service 25 copies both raw texts, concatenates them, and writes to the first
argument as a **VM word address**. Overlapping source/destination ranges work
because both source strings are read first. A dynamic-slot handle is valid as
a source but cannot serve as the destination.

Service 28 copies the last confirmed text-input string (`host+0x54`) to a VM
word address. Services 25 and 28 share `FUN_00056b78`: high byte first, through
the first NUL, including a zero terminator. An odd total byte count is padded
with another zero; bytes after the written words remain untouched. Empty text
writes a zero word. The runtime validates the entire writable extent before
changing memory and preserves signed word representation. Destination capacity
inside a valid VM region remains caller-managed, as in the original.

## Randomness and numeric bits (services 27, 50, 51)

Service 27 returns zero without drawing when its signed bound is nonpositive.
Otherwise `FUN_0009ea28` calls `FUN_0004c1bc` and returns the absolute signed
remainder by the bound. It shares the saved native LCG stream with grids and
football, described in [MINIGAMES.md](MINIGAMES.md). This is separate from the
choice panel's libc lrand48 stream. The exact historical seed of a user's old
native installation is not recoverable.

Services 50 and 51 share the numeric map used by services 44/45/52/53/54/55.
The map value is a signed **32-bit** integer; ordinary setters sign-extend
their argument and ordinary VM getters narrow their return to 16 bits.
The key remains `(s16(owner)*65536+s16(key)) mod 2^32`.

```text
50(owner,key,bit,value):
    shift = bit & 255
    mask = shift < 32 ? (1 << shift) : 0   # ARM register LSL
    map[key] = value == 1 ? map[key] | mask : map[key] & ~mask
    return 0
51(owner,key,bit):
    return (signed32(map.get(key,0)) >> (bit & 255)) & 1
```

The getter uses arithmetic right shift, including sign fill for counts >=32.
Exactly 1 sets a bit; every other value clears it. Evidence: `FUN_000965bc`,
`FUN_00095ca0`, and the common setter `FUN_00096474`.

## Dialogue notifications (service 88)

```text
arguments : text_ref:i16
result    : 0, immediately; no notification callback
queue     : one substituted Latin-1 string, panel 3 +0xf0
consumer  : next dialogue presentation (000aaa40)
```

This is the common path for stat changes, grades and upgrade messages. The
Football Star scripts use it for Strength Up, Popularity Up/Down, +1 to Grades,
and the block/running/pass upgrades. There is no stat-name lookup in the
renderer. Scripts change numeric properties and request sounds separately;
service 88 itself changes neither stats, result cells, audio nor randomness.
Repeated calls replace the queued string. Substitution happens when queued,
not when displayed. An empty string clears the queue.

The next dialogue consumes the queue, creates the notice immediately and
starts its own active-time countdown. The additional animation-delay arguments
passed by `000aaa40` are unused by `0009c814`; the notice does not wait for the
portrait or body-text reveal. Its node is attached to the current portrait
parent at child/z-order tag 25000. It is a sibling of the scaled head, so it
does not inherit that head's entrance zoom or horizontal flip. A hidden
portrait parent (narration or missing character art) also hides the notice.

### Typography and placement

`0007cbbc` constructs the notice label `002ae924` with font-registry entry 14,
`PajamaHipS26.fnt`, nominal height 16 and extra line gap 5. The font's red
lettering and white outline come from the player's APK atlas. `0009c814`
sets RGB to white, preserving those baked colors. It sets the label scale to
1 for fewer than 19 source bytes, and 0.88 otherwise. Alignment 5 is top-left,
with explicit newlines but no automatic wrapping or emphasis markers
(`0004de48` / `0004dc20`). Existing font advances, offsets and kerning apply.

In native GL coordinates the notice starts at `(-60,50)` relative to the
mode-1 portrait parent, or `(-260,50)` for mode 2. The parent center comes from
layout 17 rectangle 0x30 or 0x4e, with `000aaa40`'s `485-y` conversion. In the
runtime's downward coordinates, for portrait rectangle center `(cx,cy)`:

```text
notice_origin = (cx + (-60 if mode == 1 else -260), cy - 55)
glyph_left    = notice_origin.x + scale * font_layout.glyph_left
glyph_top     = notice_origin.y + scale * font_layout.glyph_top - rise(i,t)
```

The label has zero content size, so its half-width/height anchor adds no
translation. These positions are evaluated on the native 320×480 dialogue
canvas before scaling to the desktop window. The notice is drawn with its
portrait, rather than over unrelated panels or the host menu.

### Letter entrance, exit and input

`0009c814` starts every letter's linear `MoveBy(0,40)` simultaneously. Drawn
child index `i` has duration `30*(i+1)` ms: the first letter finishes first,
making a rising wave. Child tags count non-space glyphs across lines
(`0004d3f8`), independently of source-byte indices. Spaces and newlines still
contribute to the overall display lifetime.

For source length `N`, the scheduling variable starts at 30 ms and is
incremented after **each** source byte. The exit therefore starts at
`165*(N+1)` ms, not `165*N`. `0009c7c8` invokes `0009c750` once; the label then
fades from 255 to 0 and moves upward another 50 units over 300 ms. The linear
action updates are verified at `00136364` and `001365f4`.

```text
exit_start_ms = 165 * (N + 1)
lifetime_ms   = exit_start_ms + 300
exit          = clamp((t - exit_start_ms) / 300, 0, 1)
rise(i,t)     = scale * 40 * clamp(t / (30 * (i+1)), 0, 1) + 50 * exit
alpha         = trunc(255 * (1-exit))
```

`000a9868` hides the notice at the beginning of dialogue input, including a
tap that only completes the reveal or advances to another page. This does not
bypass either input gate or resume a still-revealing VM call. Service 39 also
clears active and queued notices when closing the panel. Expiry alone does
not acknowledge dialogue or generate a game result.

The existing save fields are sufficient: `next_dialogue_notice:string`,
`notice:string`, and `notice_ms:int` (remaining time, including the fade).
An empty active notice requires zero time; otherwise time lies in
`[0,165*(N+1)+300]`. Elapsed motion is derived from that countdown. Rendering
does not advance it, and the desktop excludes menu/unfocused time. Older
saves retain their shorter saved remaining countdown without changing VM
state; their motion is reconstructed from the corrected deadline. No save
fields or new save version are needed.

Authored tests cover replacement/substitution, unrelated stat/result/random
state, letter geometry, the long-message scale, fade, input/page gates,
save/load during each phase, malformed timers, pixel movement with an authored
font, and paused clocks. Local verification naturally completes Football
Star's service-96 encounter and reaches its service-88 Strength Up notice at
scene 25011, then renders the supplied assets at multiple animation times.
These are native-code and asset checks, not a running-original frame capture;
cross-label kerning history and native scheduler frame boundaries retain the
limitations described in [UI_FIDELITY.md](UI_FIDELITY.md).

## Scene label and dialogue emphasis (services 89, 90)

Service 90 is nonblocking. Its second argument is substituted text, or empty
when -1. Icon ID -1 removes the badge; otherwise the icon/text are retained.
`FUN_0007b97c` creates the badge from layout 67, a 171 × 60 frame 13 from the
theme pack. Initial text `Free Time` selects blue pack 204; otherwise pack 236.
Updating an existing badge retains its original skin and entrance progress.
Text color is (69,107,176) for `Free Time`, otherwise (223,163,52).

Layout node 2 centers the icon at (38,30). Text uses ArialRoundedMTBold16,
nominal height 14, gap 1, width 110; the native function has string-length and
named-label positioning exceptions, represented by `SceneBadge.text_position`.
The badge moves horizontally in 200 ms from center x=-85.5 to x=100.
Ad-free top inset is 10 (`FUN_0007d280`); the original ad-enabled path uses 55.
The desktop uses the ad-free placement. Native multiline horizontal alignment
is approximated by centering the measured block; future pixel comparisons may
refine that typography.

Service 89 sets scene byte +0x3f8 for the **next dialogue**, then completes with
zero. `FUN_000aaa40` consumes and clears it; `FUN_0007c9e8` rotates the dialogue
box independently of its text and portrait. Mode 2 starts at +20 degrees,
rotates to -20 in 70 ms, waits 2 ms, then returns to zero over 70 ms. Other
modes invert the direction and wait 5 ms. The changed-character text path
also omits its usual additional 120 ms delay. Page turns do not replay the
one-shot wobble.

## Optional device request and native stub (services 82, 99)

`FUN_000a3040` requests 1000 ms from the optional vibrator, gated by device and
settings availability. The desktop has no vibrator backend and completes
without altering music or sound state. Android's vibrator implementation is
constructed by `FUN_00102f1c` / `FUN_00108188`, using VibratorAndroidDelegate.

`FUN_00082adc`, called by service 99, contains only two ARM instructions:
`mov r0,#0` and `bx lr`. This release therefore always takes the dispatcher's
normal completion path; no wait or host +0x118 state is introduced. This is
verified native behavior, not a general policy of ignoring unknown services.

## Save schema additions (version 5)

| Field | Contract |
| --- | --- |
| `engine.character_picker` | Null, or the selector model; required exactly when pending service 78 |
| `characters` | 1–5 signed character IDs copied from the pending VM arguments |
| `order` | Permutation of original indices; first entry is selected |
| `portraits` | One motion object per original character, independent of order |
| motion `start`, `end` | Triples of finite `(x,y,scale)` floats within the native positions/scales |
| motion `elapsed_ms` | Integer 0–50 |
| motion `opacity` | 255 or 91 |
| pending picker `details.text` | Substituted prompt, checked against its retained VM frame |
| `engine.scene_badge` | Null or `{asset_id:s16>=0,text:string,blue:bool,elapsed_ms:0..200}` |
| `engine.next_dialogue_wobble` | Boolean, consumed by the next dialogue |
| pending dialogue `details.box_wobble` | Optional boolean; absent in older saves |
| `engine.dialogue_animation.wobble_direction` | -20, 0 or 20; uses existing elapsed clock |

Older versions migrate missing fields to null/false/zero, preserving choices,
random states, pending frames and page/reveal progress. Older unsupported
service-78 stops are initialized from their original arguments. Renderers do
not write VM results or advance clocks. Pausing/focus loss stops active time.

## Loading overlay (service 91)

```text
service 91(wait: s16) -> R = 0
```

This is a timed application overlay, not a choice, download request, or arbitrary
acknowledgement. `FUN_0009fe3c` sets application `+0x6ac36` and opens the overlay
through `FUN_0008d43c`, using string bank 13 entries 31 and 35 ("Loading" and
"Please wait..."). It always sets host `+0x118`, which gates further VM execution.

| Argument | At dispatch | At overlay completion |
| --- | --- | --- |
| `wait == 0` | Pop the one-word argument frame and set R=0 immediately | Release the host execution gate; do not pop again |
| `wait != 0`, including negative values | Retain the VM yield and its argument frame; set host `+0x84` | Pop the frame, set R=0, clear host wait/pause flags |

Neither branch writes UI result cell 0, changes relationship values, consumes
randomness, or schedules another scene. Both prevent the next VM instruction
from running until the overlay closes. `EngineAction.completed` remains false
while this application work is pending, even if its nonwaiting VM call has
already completed.

`FUN_0008e7d0` increments the application's floating-point millisecond counter
at `+0x6ac30`. `FUN_0009ea70` checks **counter > 3000**, overlay visible, and the
service-owned flag, then clears host `+0x118` and calls `FUN_000843c8`. That helper
resets the counter/visibility, restores application input, detaches both text
nodes and the loading sprite, removes the two panels, and clears the service
flag. The host updater then completes the retained frame if `+0x84` was set.
The `1500` argument visible at the constructor call is unused by that function;
it is not the completion threshold. Disassembly at `0x0008e8c0` confirms a float
addition, despite the decompiler presenting some counter stores as integer casts.

The session uses active integer milliseconds. At 3000 ms the overlay remains;
the next positive tick completes it. Save/load and foreground pauses preserve
the timer. Overshoot is not applied to the following mini game or screen.
Player acknowledgement is rejected. The desktop retains its host pause/save
shortcuts while the original loading overlay has no confirm or cancel button
in the in-episode application state.

Presentation uses user-supplied artwork and fonts:

| Element | Native binding / top-origin placement |
| --- | --- |
| Upper panel | Layout 50, 320×150, at (0,170); original blue skin 204 |
| Lower panel | Layout 22, 350×60, at (-20,287); node 13 and its subtree hidden |
| Title | Registry font 6, ArialRoundedMTBold20, nominal height 20, RGB (41,104,221) |
| Message | Registry font 5, ArialRoundedMTBold16, nominal height 15, width 300, same color |
| Animated icon | Common pack 126 frames 23–27, centered at (155,317) |

`FUN_0008952c`, `FUN_00177458`, and `FUN_00136a30` establish **500 ms per frame**,
five frames and a 2500 ms repeating animation. This animation does not determine
when the VM resumes. Download/cancellation overlays reached from other native
application states are separate contracts. The desktop currently draws these
panels over the existing scene background; retention of underlying native
dialogue/widget objects across application overlays remains a fidelity detail.

## Save schema additions (version 6)

| Field | Contract |
| --- | --- |
| `engine.loading` | Null or `{blocking:bool, elapsed_ms:int[0..3000]}` |
| Pending loading screen | `{name:"loading", details:{}}` |
| Loading `vm.pending` | Retained service-91 yield for nonzero argument; null for argument zero |
| Dialogue `details.relationship` | Null or the `RelationshipChange` fields in [UI_FIDELITY.md](UI_FIDELITY.md#npc-relationship-indicators) |
| `engine.dialogue_animation.relationship` | Null or `{change:RelationshipChange, delay_ms:int[0..850], elapsed_ms:int[0..duration]}` |

For service 91(0), loading a save validates the completed instruction immediately
before the PC, R=0, and the popped zero argument still present in stack backing.
It reconstructs the screen's request description without creating another VM
yield. Both compact and register-count yield opcodes are supported. Timers,
pending-screen identity, native arguments and relationship cache correspondence
are checked before accepting the save.

Versions 1–5 receive null new state. An older unsupported service-91 checkpoint
initializes the overlay from its retained frame without replaying earlier script
instructions. Older dialogue saves retain their reveal/page progress; relationship
icons are initialized settled and their caches populated without replaying sounds
or inventing historical gain/loss animations. Original player files are not
rewritten just by loading them.

## Verification and remaining scope

Authored tests cover packed-string padding and overlap, invalid extents,
formatting/scratch aliasing, shared random replay, high-bit updates, sprite
selection versus confirmation, original index mapping, mid-motion saves,
legacy migration, original art, resized release input, and paused clocks.
Local tests exercise all five Homecoming Queen appearances and Football Star
through character creation and its first classes with the original scripts.

Football Star's service 91 at scene 25006, PC 1245 now completes into service 94
at PC 1270. The regression route plays both football halves through public
tap/tick input and returns to Howard's original dialogue. Authored tests cover
both loading argument forms, the strict timer boundary, retained/popped frames,
older checkpoints, malformed saves, original animation frames and paused input.
Relationship tests cover icon selection, counts, native cache writes and sounds,
staggered gains, falling losses, dialogue delays and exact mid-animation restore.
Extraction of all story scripts is complete; full eight-week playback is not
yet established.
