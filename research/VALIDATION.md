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
