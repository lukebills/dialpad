# First build validation — 14 September 2026

- Local Git repository created at `/Users/lukebills/projects/dialpad`; no remote publication.
- 22 unit tests passed: upstream protocol fixtures, validation boundaries, authenticated HTTP handling, immutable expiring one-use previews, no automatic write retries, partial failures, and transport selection. Hardware was mocked for these tests.
- JavaScript syntax check passed.
- Browser smoke test passed on Chrome with the source launcher, then the packaged Apple Silicon Mac app. Verified device discovery, six-key editor, dial actions, preview/cancel, profile export/import, rejection of hidden mouse modifiers, scratch key input, and mobile width. Test intercepted and prohibited all Apply requests.
- Read-only hardware check identified USB `1189:8890`, interface 1, interrupt OUT endpoint `0x02`, 64-byte packets. Open/claim/release/close succeeded. No driver detachment, reset, firmware update, or device programming.
- Packaged Mac application built with Python 3.13.13, PyInstaller 6.22.3 and libusb 1.0.30. Browser discovery passed using the bundled library. Approximate app size 20 MB.
- Wispr Flow chosen by the user; all starter profiles use its hands-free toggle, not native OS/Codex dictation. The Mac shortcut requires matching setup inside Flow.

Still unverified: physical programming outcome and persistent storage on this firmware; physical key ordering; dial direction under host scroll settings; actual Wispr insertion in the user's terminal; Windows packaging and HID behavior. A build workflow is supplied for Windows, but no Windows executable or Windows test result is claimed.

Screenshot: `ui-preview.png`. Protocol and shortcut sources are recorded in the adjacent reports and `core/` notes.

## Shortcut correction follow-up

Added modifier-only Control+Option encoding and explicit push-to-talk/custom hands-free selection after the user's shortcut correction. 23 unit tests pass. Rebuilt Mac app passed the browser smoke test, including modifier-only editing and review text. No hardware writes. Physical hold/release remains unverified.

## Desktop companion and setup cycling

Added persistent saved setups, explicit preview/enable, app-managed F18 cycling, a native Mac WebKit window, menu-bar layout and tooltip, optional floating layout panel, and brief on-screen change banners. The Windows companion uses Tk and RegisterHotKey; it remains untested on Windows.

- 30 unit tests pass. New checks cover reviewed cycle snapshots, no writes during save/preview, debounce and wraparound, persistent setups without automatic rearming, failure disarming with unknown hardware state, desktop readiness, common hardware layer, and refusing queued writes.
- Packaged Chrome smoke passed, including isolated saved-setup editing/removal and cycle preview/cancel. All Apply requests were blocked; saved-setup API calls were mocked to preserve user files.
- Native packaged smoke passed: WebKit loaded six keys, the desktop registered F18 successfully, and the USB device was discovered. Cycling stayed disabled. Native host exited cleanly.
- Mac bundle built successfully and passed `codesign --verify --deep --strict`.

No keypad bindings were written during this feature's implementation or verification. Physical dial-triggered switching, notification timing during a real transfer, and resulting keyboard actions still require an explicit enable and physical test. Each switch programs bindings; this is not a firmware layer-switch command. Firmware write endurance is unknown, so the UI describes this as occasional setup switching.

## Preloaded everyday layouts

Bundled Media, Web browsing, Word desktop and Apple Mail layouts now populate a fresh Mac saved-layout library automatically. Existing libraries gain missing defaults within the eight-slot limit. The Windows catalog includes the first three; Apple Mail is Mac-only. Per-layout preload history retains user edits, renames and removals; unreadable user libraries are not overwritten.

34 unit tests pass, including fresh-install preloading, all bundled profiles passing the packet validator, upgrade preservation, layer matching, restart/edit/removal persistence, and full/corrupt library handling. The rebuilt packaged browser smoke test passed with an isolated temporary settings directory: all four defaults appeared without Save, their editors loaded correctly, Media showed volume on its dial, and Apple Mail retained the user's Flow chord. Existing review, export/import, saved-cycle and responsive checks passed. All hardware Apply requests remained blocked. The rebuilt Mac bundle passed strict deep code-signature verification. No physical keypad changes or target-app shortcut execution were performed.

## App icon and quiet menu-bar updates

Added an original six-key-and-dial SVG, rendered PNG, multi-resolution Mac ICNS and Windows ICO. Mac packaging references Dialpad.icns; the native host loads the matching PNG for its Dock icon, and the editor uses the SVG. The menu bar has a matching monochrome keypad symbol. Removed automatic floating notification panels entirely; setup changes and error details remain in the menu bar, tooltip and editor. The optional user-opened layout panel remains available.

All 34 unit tests, packaged browser smoke and native Mac smoke passed. Verified the bundle icon reference and native icon asset, and strict deep code-signature verification passed. No hardware writes were performed.

## Visual live keypad previews

Replaced the Mac menu's text-only binding list and floating window with a shared native vector keypad view: two rows of three keys, labelled dial press, and two rotation labels. The expanded editor header now mirrors that arrangement with responsive HTML/CSS. Labels, shortcuts and media/scroll dial actions come from the current enabled setup, not unapplied editor changes. Cycling-off and disconnected views clear active mappings and retain explanatory state. Accessibility text and full-detail tooltips accompany the native graphic.

Packaged browser smoke passed with mocked active Media bindings: six visual keys, Next setup dial press, volume rotation labels, and no horizontal overflow at 390px. Native rendering was inspected using a Word fixture without registering a hotkey or writing to USB. The finished native packaged smoke and strict deep code-signature check passed. Screenshots: `native-layout-preview.png` and `live-layout-preview.png`. No hardware bindings were written during verification.

## Coding dial arrow keys

Changed all Claude/Codex starters to emit keyboard Up on counterclockwise rotation and Down on clockwise rotation. Updated the user's existing saved Claude Code and Codex terminal profiles, retaining their other bindings; saved a local pre-change settings backup. Everyday layouts retain their existing rotation actions. Packaged UI smoke verified the arrow editor values and passed its existing checks with hardware Apply blocked. Strict deep bundle signature verification passed. Hardware activation still requires Review & enable.

## Dashboard and resumable companion — 2026-09-15

Replaced the everyday editor-first screen with live keypad, independent template library, and drag/reorder cycling list. Detailed editing is collapsed by default, with Create new setup and template Edit entry points. Connection discovery refreshes every four seconds and keeps an unchanged review valid. Direct programming reviews explain that they stop cycling.

A successfully enabled cycle now persists its reviewed snapshot and active index. Relaunch restores that state only after native hotkey registration; restoring makes no USB writes. Stop and programming failures clear the resume marker. The marker is also removed before a switch, so an interrupted transfer cannot restore a possibly partial layout. Mac launches reuse the existing companion, and Run in background hides the editor while retaining the menu bar. Windows close minimizes the companion; Windows remains untested.

Added optional Alternate Copy / Paste on one key per profile. It encodes F19 and is available through an enabled cycle, including a single-template cycle. The native companion sends Copy first, then Paste, resetting on setup changes or relaunch. Mac requests Accessibility permission on first use; no clipboard contents are read. Existing Paste bindings are preserved. Physical shortcut delivery, Accessibility approval and Windows behavior still need user testing.

Validation: 39 unit tests passed; packaged Playwright smoke passed including template drag/drop, reorder buttons, optional Copy/Paste selection, auto-refresh preserving preview, review/cancel, and responsive layout. Native packaged smoke passed with F18/F19 registered, background-button hiding and editor reopening verified, and read-only keypad discovery. Strict deep bundle signature verification passed. Launching the actual app twice reused the existing companion and requested its window reopen. No hardware writes or synthetic Copy/Paste events were performed during verification. Actual app reopened with cycling awaiting review; saved user templates were preserved.

## Clipboard options — 2026-09-15

Added plain-text/original-format copy modes, configurable idle return to Copy (10 seconds by default), and optional double-tap Cut. Double-tap mode delays single actions 320 ms so the first tap does not Copy/Paste before Cut. Cut arms Paste; idle expiry, layout changes, and relaunch restore Copy. App changes cancel pending actions. Copy/Cut waits for clipboard change before advancing, up to one second; unchanged clipboard leaves the next action on Copy. Non-text/image/file items are preserved. Clipboard text is used locally only when stripping a newly copied text result; it is not logged, saved, or sent to the backend. Existing actions missing these fields use plain text, 10 seconds, and Cut defaults.

44 Python tests pass, including gesture phase/timing/validation tests. Native pure Swift gesture checks pass in the optimized build (preconditions remain enabled). A private named pasteboard test passed for Unicode text preservation, HTML removal, and file/image preservation; it never accessed the general clipboard. Packaged UI tests passed including changing and exporting/importing all three options. Native background/hotkey smoke and strict deep signature verification passed. No hardware programming or synthetic Copy/Paste/Cut into user applications was performed. Physical key behavior and Windows runtime remain unverified.

Clipboard API references: [Apple NSPasteboard](https://developer.apple.com/documentation/appkit/nspasteboard/) and [Microsoft clipboard operations](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-operations). The Windows companion uses its existing Tk clipboard ownership support and checks the Windows sequence number before converting new text; file and image formats are excluded.

## Multi-tap keys and quieter window (2026-09-16)

The Mac title bar now uses the editor background colour. Removed the separate floating layout window and its menu command; the menu-bar diagram remains. Windows starts its companion minimized.

Added six independent multi-tap bindings with per-key 100–1000 ms timing (350 ms default). Single/double wait for the gap; triple fires immediately. Defaults are plain-text Copy, Paste, Cut, with configurable clipboard, keyboard, mouse and common media actions for each tap. Existing alternating bindings can explicitly convert in the draft editor; saved templates and hardware are preserved until save/review/enable. F13–F17/F20 are per-key triggers, alongside F18 cycling and legacy F19. Restricted tap shortcut keys prevent recursive trigger emission. Foreground-app and cycle context guards cancel pending actions.

51 Python tests pass. Packaged UI smoke passes including per-tap editing, conversion, import/export, timing validation and mobile sizing. Packaged native action-recording test passes for single/double/triple exclusivity, independent keys, cancellation and focus guards, with no input emitted. Native window smoke confirms matching title bar, absence of floating panel, F13–F20 registration, background hide/reopen and read-only keypad discovery. Strict deep signature verification passes. Physical key delivery, user Accessibility approval and Windows execution remain untested. No hardware writes or user clipboard access were performed by these checks.

Native events use [Apple Quartz keyboard events](https://developer.apple.com/documentation/coregraphics/cgevent/init(keyboardeventsource:virtualkey:keydown:)) and the existing local clipboard handling.

## Repeated device-control permission prompts (2026-09-16)

Inspection found both the app and native helper have ad-hoc designated requirements tied to their individual binary hashes; `security find-identity -v -p codesigning` reported no valid identities. macOS may therefore retain a visible but stale permission entry after rebuilds. The previous runtime also called AXIsProcessTrustedWithOptions with prompting enabled on every attempted gesture.

The runtime now uses AXIsProcessTrusted for silent checks on every action and periodic state refresh. A persisted prompt gate allows only the initial system prompt; later blocked actions leave a quiet menu status. A grant takes effect without a cached denial or automatic input replay. The menu offers targeted permission settings help and Finder reveal for the current app. No permissions are reset, granted, or bypassed programmatically.

The build accepts DIALPAD_SIGNING_IDENTITY for consistent app/helper signing; the existing ad-hoc fallback warns about renewal. A stable signed build remains dependent on an installed signing identity, and actual consent/recovery needs a user check. Apple documents version-specific ad-hoc requirements in [TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements) and asynchronous prompting in [AXIsProcessTrustedWithOptions](https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions).

Validation: 51 Python tests, packaged UI smoke, packaged native window/background/hotkey smoke, strict deep signature verification and the packaged permission-state test passed. The permission-state test covers repeated blocked attempts, a grant, revocation and relaunch without opening OS prompts or emitting input. No hardware writes or user clipboard changes occurred. Persistent approval across signed updates is not claimed or tested.
