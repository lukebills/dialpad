# Dialpad

A local six-key + dial configurator for AI coding. Built for the `1189:8890` CH57x-2 keypad family, with Claude Code and Codex starter layouts. Native Mac window and menu-bar companion, local USB connection, no cloud service or account.

## Run on this Mac

Open `dist/Dialpad.app`. The editor opens in its own Mac window. Its menu-bar item shows the current cycling setup: click for a visual six-key-and-dial preview or **Show / hide floating layout**. Closing the editor keeps the companion running; **Quit Dialpad** stops both. No installation or Python setup is needed for the packaged app.

The source version runs with Python 3.10+: `python3 app.py`. macOS source development additionally needs libusb; the packaged app includes it. Windows uses built-in HID APIs. Neither route executes the manufacturer's software.

## First use

1. Plug the keypad in by USB. Click Refresh if needed.
2. Load the Claude Code terminal, Codex terminal, or Codex desktop starting layout, and choose Mac or Windows. Loading a layout edits the app only.
3. Choose **Wispr Flow behaviour**. The default Mac hands-free binding matches your configured **Control + Command + Option**, with **no extra key**. Tap once to start and again to stop and paste. Your alternative Flow triggers are Fn + Space, middle click, or double-tap Fn. To use middle click instead, change Key 1 to Mouse → middle click. This editor cannot encode Apple Fn. The optional push-to-talk choice sends Control + Option; physical hold/release still needs testing. Windows hands-free uses Control + Windows + Space; verify it in Flow settings. Dialpad triggers Flow; it does not transcribe audio itself.
4. Click a key and choose its action or record a shortcut. For modifier-only shortcuts, select **No key · modifiers only** and tick the modifiers. The dial supports real mouse-wheel up/down and an independent press action.
5. Start with **Selected control only**, click **Review changes**, verify the proposed binding, then **Apply to keypad**. Test it in the scratch area and your coding app. Key positions and wheel direction need a physical check.
6. Export your profile to keep a copy. Import restores the editor settings; Apply writes them to the keypad.

The initial layout is Wispr Flow, Enter, Escape, New line, Paste, and Transcript (Claude terminal) or Tab (Codex terminal). Dial rotation scrolls and its press sends Tab. Desktop profiles use separate shortcuts. Escape has context-specific behavior, not a universal rejection action. See [shortcut research](research/KEY-LAYOUT.md).

Profiles are **not** read from the hardware. Applying replaces the selected controls on the selected layer. The app cannot back up the existing device configuration, verify it by read-back, or automatically roll back an interrupted write. A completed transfer must be checked on the physical keypad. Layers 2 and 3 are only useful if your hardware supports switching layers. Profiles do not switch automatically with the foreground application.

## Cycle setups with the dial

1. **Media, Web browsing, Word and Apple Mail are already saved on first launch on Mac.** You do not need to create them. Upgrading adds them alongside existing setups, with room for eight total. Windows includes Media, Web browsing and Word; Apple Mail is Mac-only.
2. Choose a saved setup and **Edit saved** to customize it, or add a coding layout with **Save current setup**. Their list order is the cycling order. Use the same hardware layer for every setup. Your edits and removals survive restarting; Starting layout retains the bundled originals if you want to restore one.
3. Select the keypad and click **Review & enable dial cycling**. Review the entire cycle, then **Apply to keypad**. This immediately sends the first setup and replaces the dial press with **F18 → Next setup**.
4. Press the dial to send the next setup. The Mac menu-bar label and editor header update quietly to show the last successfully transferred layout. Click the menu-bar icon for a miniature keypad with labels and shortcuts placed on the keys. The optional floating panel and expanded editor header use the same physical arrangement. Turn the dial to use that setup's scrolling actions. Physical results still need testing.

Cycling is handled by the running app, not an internal firmware layer-switch command. Each switch rewrites all nine bindings on the same layer. The protocol provides no read-back, persistence guarantee, or write-endurance specification; use it for occasional setup changes. Allow at least 1.2 seconds between presses; presses during a transfer are ignored. A failed transfer stops cycling and marks the device state unknown, with no retry or rollback.

The app reserves **F18 globally** while it is open. F18 from another keyboard also switches setups; the OS hotkey API cannot distinguish which keyboard sent it. No general keyboard activity is recorded. If another app owns F18, cycling cannot be enabled. On Mac the hotkey uses Carbon RegisterEventHotKey; it does not require a general input-monitoring permission.

**Stop cycling** or **Quit** leaves the last written bindings, including F18, on the keypad. Apply a normal editor layout to restore the dial press to Tab or another action. Cycling is off after every launch until reviewed and enabled again. Saved edits do not alter an already enabled cycle: review and enable again to replace its snapshot.

The Media dial adjusts volume; the other everyday dials scroll. Word and Apple Mail retain Wispr Flow on Key 1. Browser shortcuts target Chrome, Word targets its desktop app, and Mail targets Apple Mail. Focus the target application before using its bindings. See [the complete everyday key layout](research/KEY-LAYOUT.md#preloaded-everyday-layouts).

Saved setups live in `~/Library/Application Support/Dialpad/setups.json` on Mac or `%APPDATA%/Dialpad/setups.json` on Windows. Export individual profiles for sharing or backup. A neighboring `preloaded-layouts.json` file records which defaults have already been installed, so deleted defaults stay deleted. If eight slots are already occupied, bundled originals remain in Starting layout and missing defaults are added on a later launch if space is freed. Unsaved editor changes are still temporary. Setup changes and errors appear in the menu bar and editor, without popup notifications.

## Portability and current limits

- macOS: native IOKit enumeration plus bundled libusb for the raw programming interface. No driver replacement, firmware flashing or manufacturer executable. Packaged builds match the Mac architecture used to build them.
- Windows: native HID output path implemented, but not tested on Windows hardware. Some firmware versions may not expose a compatible native programming interface. Do not assume the Mac-tested raw transport proves Windows compatibility.
- Mac builds use a native WebKit editor, menu bar, and floating panel. Windows uses a small always-on-top companion with a browser editor and global F18 hotkey; this Windows companion has not yet been tested on Windows. Both communicate only with a server bound to `127.0.0.1` using a per-launch secret. Internet is not required.
- The local build is ad-hoc signed, not Apple-notarized. Public distribution with a smooth first launch needs appropriate signing/notarization; we do not disable Gatekeeper.
- Only the reserved F18 hotkey is handled globally. There is no background dictation engine, arbitrary script execution, or automatic foreground-app switching. The scratch test area only sees input while it has focus.
- Save current setup or export before quitting to retain editor changes. Saved profiles are app settings, not hardware backups.

## Develop and build

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build.py
```

Mac builds also require the Xcode command-line tools to compile the Swift desktop host. Source-only launches use the browser unless the native host is supplied; `--no-browser` is available for test harnesses.

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Build on each target OS; PyInstaller does not cross-compile. Windows output is `dist/Dialpad/` (keep the EXE and its supporting files together). Mac output is `dist/Dialpad.app`. The GitHub Actions workflow can build both after this repository is hosted on GitHub; no remote is configured automatically.

The app icon is an original editable SVG in `ui/icon.svg`. Generated Mac, Windows and PNG icons are in `assets/`; `assets/render_icon.py` regenerates them with Playwright/Chrome and the macOS icon tools. The native host also uses a small template keypad symbol in the menu bar.

The frontend is plain HTML/CSS/JavaScript. `app.py` handles authenticated local API requests, validation, and one-use expiring write previews. `core/protocol.py` encodes validated packets without device I/O. `core/transport.py` accesses only the supported keypad ID and reports failures without automatic retries. Tests mock hardware; they do not program the keypad.

## Sources and licences

Protocol derived from the MIT-licensed [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool); its attribution is in `core/THIRD_PARTY_LICENSE.txt`. Bundled libusb is LGPL-2.1-or-later and dynamically loaded; see its licence and source/replacement instructions in `core/LIBUSB-LICENSE.txt` and `core/TRANSPORT-NOTES.md`. Python and PyInstaller bundle their runtime notices in the distribution where applicable.

The supplier ZIP was inspected only as data and is excluded from Git and builds. See [initial review](research/REVIEW.md) and the archive hash inventory. It was never executed and has not been certified malware-free.
