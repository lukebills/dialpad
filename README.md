# Dialpad

Dialpad is a customizable, local app for **mini six-key keyboards with one clickable rotary dial**—the inexpensive USB macro keypads commonly sold on AliExpress as “6 Keys 1 Knob” or “Mini 6-key keyboard”. It provides a simpler alternative to the manufacturer's configuration software, with editable keys, dial actions and layouts for AI coding, media, browsing, Word and email.

The source code is available here to customize and build yourself. The packaged apps are designed for **Windows and macOS**: a portable **EXE with its supporting folder on Windows**, and an **app bundle on Mac**. You do not need Python or the manufacturer's software to run a package. It works locally with no cloud account.

### Compatible keyboards

This project targets the **CH57x-2 family with USB vendor/product ID `1189:8890`**, using six keys and one dial that turns and presses. That is the family used during development. AliExpress sellers can reuse the same product photographs for different hardware or firmware, so six keys and a knob alone do **not** guarantee compatibility. Confirm the USB identity and test discovery before applying a layout. Windows programming on physical hardware still needs validation; Mac testing does not establish support for every similar keypad.

### Download or update on Windows

Run this once in **Windows PowerShell** to download the latest published app,
verify its checksum, and create **Dialpad** and **Update Dialpad** in your Start menu:

```powershell
curl.exe -fL "https://github.com/lukebills/dialpad/releases/latest/download/Update-Dialpad.ps1" -o "$env:TEMP\Update-Dialpad.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\Update-Dialpad.ps1"
```

After that, open **Dialpad** from Start. Use **Update Dialpad** for later releases.
The updater briefly opens PowerShell; the app itself opens a normal Windows window
with the same editor as Mac, without a terminal or browser tab. Close the window
or choose Run in background to leave the keypad companion in the system tray.
Double-click the tray icon to reopen it; its menu shows the active setup and Quit.

The updater installs only into `%LOCALAPPDATA%\Programs\Dialpad`, closes the old
app gracefully, keeps older versions for rollback and preserves your setups in
`%APPDATA%\Dialpad`. No administrator rights are requested. It does not install
a service, schedule updates, or change the computer's PowerShell execution policy.
Run it with `-DesktopShortcut` if you also want a desktop shortcut.

For a completely manual portable download, get the Windows ZIP from
[GitHub Releases](https://github.com/lukebills/dialpad/releases/latest), extract the
**whole archive**, and double-click `Dialpad/Dialpad.exe`. Keep all supporting files.
You can move the extracted folder; settings remain separate. Windows executables
are unsigned, and workplace policies may restrict them. Checksums accompany each ZIP.

The Windows window requires .NET Framework 4.6.2+ and Microsoft Edge WebView2
Evergreen Runtime. If WebView2 is missing, Dialpad explains how to get it from
[Microsoft](https://developer.microsoft.com/microsoft-edge/webview2).
The runtime supports [per-user installation](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
without an elevated installer. Dialpad does not silently install it. After the
runtime and app are available, the editor works locally without internet.

For Mac, download the archive matching your Mac's architecture and open `Dialpad.app`. The GitHub-built Mac app is ad-hoc signed and not notarized. Local development builds can use your own configured Apple signing identity. **macOS device-control permission is required for app-managed key actions.**

## Run on this Mac

Open `dist/Dialpad.app`. The editor opens in its own Mac window. Its menu-bar item shows the current cycling setup: click for a visual six-key-and-dial preview. Closing the editor keeps the companion running; **Quit Dialpad** stops both. No installation or Python setup is needed for the packaged app.

The source version runs with Python 3.10+: `python3 app.py`. macOS source development additionally needs libusb; the packaged app includes it. Windows uses built-in HID APIs; source development also requires building its native window with `python scripts/build_windows_window.py` on Windows. Neither route executes the manufacturer's software.

## First use

1. Plug the keypad in. Connection discovery refreshes automatically.
2. Choose a setup in the **Live setup** dropdown, or **Add new**. Click any key or dial action to edit it in the side panel.
3. Edits save automatically after a short pause. **Saved in app** confirms persistence; invalid or conflicting changes show **Not saved**. Setup settings holds the name, starting layouts, Mac/Windows choice, Wispr Flow options, import/export, layer and device. Mac Flow hands-free defaults to **Control + Command + Option** with no ordinary key. Fn itself cannot be encoded.
4. Return to **Dial cycling**, tick the setups to include, and order them with the arrows. Click **Apply to keypad** and review the changes. The Enabled checkbox can start that review or stop the active cycle.
5. Test the physical keys. The scratch area and individual-control apply are under **Test & advanced tools**. Autosave retains app settings only; programming the keypad is a separate explicit Apply.

The initial layout is Wispr Flow, Enter, Escape, New line, Paste, and Transcript (Claude terminal) or Tab (Codex terminal). In Claude and Codex layouts, dial rotation sends Up/Down arrow keys and its standalone press sends Tab. Desktop profiles use separate shortcuts. Escape has context-specific behavior, not a universal rejection action. See [shortcut research](research/KEY-LAYOUT.md).

Profiles are **not** read from the hardware. Applying replaces the selected controls on the selected layer. The app cannot back up the existing device configuration, verify it by read-back, or automatically roll back an interrupted write. A completed transfer must be checked on the physical keypad. Layers 2 and 3 are only useful if your hardware supports switching layers. Profiles do not switch automatically with the foreground application.

## Cycle setups with the dial

1. **Media, Web browsing, Word and Apple Mail are already saved on first launch on Mac.** You do not need to create them. Upgrading adds them alongside existing setups, with room for eight total. Windows includes Media, Web browsing and Word; Apple Mail is Mac-only.
2. Choose a setup directly from **Live setup** and edit its keys; the template library and separate detailed editor are gone. Names and valid key changes save automatically. Add new creates an unchecked setup. All cycling setups must use the same hardware layer.
3. Tick each desired setup in **Dial cycling**, reorder with arrows, and click **Apply to keypad**. Review the cycle, then apply. This sends the first setup and makes dial press **F18 → Next setup**.
4. The menu bar and “On keypad” status show the last successfully transferred setup. When you are not editing a key or holding unsaved changes, the editor follows physical cycle changes. Picking a setup in the dropdown edits it without programming hardware.

Cycling is handled by the running app, not an internal firmware layer-switch command. Each switch rewrites all nine bindings on the same layer. The protocol provides no read-back, persistence guarantee, or write-endurance specification; use it for occasional setup changes. Rapid presses are queued by the desktop companion and processed one at a time, without an artificial cooldown. Each press advances one setup; the display follows completed transfers. A failed transfer stops cycling and marks the device state unknown, with no retry or rollback.

The app reserves **F13–F20 globally** while running. F18 switches setups; F19 handles the legacy alternating Copy / Paste action; F13–F17 and F20 handle multi-tap on keys 1–6. F18 from another keyboard also switches setups; the OS hotkey API cannot distinguish which keyboard sent it. No general keyboard activity is recorded. If another app owns a reserved shortcut, cycling cannot be enabled. On Mac the hotkey uses Carbon RegisterEventHotKey; it does not require a general input-monitoring permission.

Clearing **Enabled** or **Quit** leaves the last written bindings, including F18, on the keypad. Apply a normal editor layout to restore the dial press to Tab or another action. The last enabled cycle resumes after relaunch once the companion registers its hotkeys; restoring state makes no USB writes. Clearing Enabled clears the saved active cycle. A normal individual-key Apply also stops cycling, and its review explains this. If the keypad was disconnected, changed externally, or a transfer failed, review and enable again. Saved edits do not alter an already enabled cycle: review and enable again to replace its snapshot.

The Media dial adjusts volume; the other everyday dials scroll. Word and Apple Mail retain Wispr Flow on Key 1. Browser shortcuts target Chrome, Word targets its desktop app, and Mail targets Apple Mail. Focus the target application before using its bindings. See [the complete everyday key layout](research/KEY-LAYOUT.md#preloaded-everyday-layouts).

Saved setups live in `~/Library/Application Support/Dialpad/setups.json` on Mac or `%APPDATA%/Dialpad/setups.json` on Windows. Export individual profiles for sharing or backup. A neighboring `preloaded-layouts.json` file records which defaults have already been installed, so deleted defaults stay deleted. If eight slots are already occupied, bundled originals remain in Starting layout and missing defaults are added on a later launch if space is freed. Invalid edits that report Not saved are temporary; correct them before quitting. Setup changes and errors appear in the menu bar and editor, without popup notifications.

The everyday screen is one editable keypad with a setup dropdown. The side panel switches between key options and cycling checkboxes. Connection discovery refreshes every four seconds without invalidating an unchanged review.

On Mac, **Run in background** or closing the window leaves the menu-bar companion running. Reopen it from the menu bar or launch Dialpad again; a second launch brings the existing editor forward. This single-instance behavior applies on both Mac and Windows. **Quit** ends the companion. This does not install a login item or start it automatically after a Mac reboot. On Windows, closing the editor hides it to the system tray and keeps the companion running. Double-click the tray icon or launch Dialpad again to reopen it.

Choose **Multi-tap** for any of the six keys to assign **Single tap**, **Double tap**, and **Triple tap** independently. Defaults are Copy, Paste, and Cut with plain-text copying. Each action can instead be a keyboard shortcut, mouse action, or common media control. The adjustable gap between taps defaults to **350 ms** (100–1000 ms). Single and double actions wait for this gap to expire; a third tap runs immediately. Each key has its own counter, and completed gestures always start fresh. There is no alternating phase or idle reset to remember.

Existing alternating bindings have a **Convert to multi-tap** button in the editor. Conversion changes only the draft and retains the formatting and modifier preferences. Wait for **Saved in app**, then **Apply to keypad** in the cycle to program the new triggers. Dialpad must keep running in the background; Mac requires Accessibility permission to deliver actions. Pending taps are cancelled on layout changes and discarded if focus moves to another app. The separate floating layout window has been removed; the menu-bar preview remains.

Legacy alternate mode remains available for existing profiles:

To alternate Copy and Paste, edit a key and choose **Alternate Copy / Paste**, wait for autosave, then apply its cycle (a single template is supported). The first press sends Copy, the second Paste, then repeats. It resets to Copy on setup changes or relaunch. One alternating key is allowed per setup. Mac uses Command; Windows uses Control (a terminal template can retain Control + Shift). On Mac the first use requests Apple Accessibility permission so Dialpad can send the shortcut to the focused app. Without permission the phase does not advance. Plain-text mode reads the newly copied text locally to remove its rich formats; clipboard text is never logged, saved to disk, or sent to the server. If Copy/Cut does not change the clipboard within one second, the next tap stays on Copy. This feature still needs physical testing and Windows validation.

Clipboard options are inside the key editor:
- **Copy formatting:** Plain text (default) or Keep original formatting. Plain text removes rich text/HTML from a new text copy or cut; image and file clipboard items are preserved.
- **Return to Copy after inactivity:** defaults to 10 seconds; choose 5/10/30/60/120 seconds or Never. This resets the next action, not the clipboard contents.
- **Double-tap action:** Cut (default) or Off. With Cut enabled, a single tap waits 320 ms; two taps in that window send only Cut. Cut leaves the next action on Paste until the idle reset. With it off, each tap acts immediately.

Switching layouts or relaunching resets to Copy and cancels pending gestures. A foreground-app change cancels a pending action rather than sending it into the newly focused app. Clipboard conversion briefly waits for the Copy/Cut result; further taps during that conversion are ignored. The app does not continuously monitor clipboard contents. Saved older Copy/Paste actions use the new defaults when their options are absent.


## Portability and current limits

- macOS: native IOKit enumeration plus bundled libusb for the raw programming interface. No driver replacement, firmware flashing or manufacturer executable. Packaged builds match the Mac architecture used to build them.
- Windows: native HID output path implemented, but not tested on Windows hardware. Some firmware versions may not expose a compatible native programming interface. Do not assume the Mac-tested raw transport proves Windows compatibility.
- Mac builds use a native WebKit editor and menu bar. Windows uses a native WinForms/WebView2 editor, a system-tray icon and global hotkeys; Tk runs hidden only for clipboard and timer services. Physical keypad programming still needs validation. Both communicate only with a server bound to `127.0.0.1` using a per-launch secret. Internet is not required.
- The local build uses the configured Apple Development signing identity and is not Apple-notarized. Public distribution with a smooth first launch needs appropriate signing/notarization; we do not disable Gatekeeper.
- Only the reserved F13–F20 hotkeys are handled globally. There is no background dictation engine, arbitrary script execution, or automatic foreground-app switching. The scratch test area only sees input while it has focus.
- Check **Saved in app** before quitting; export remains available for backup. Saved profiles are app settings, not hardware backups.

## Develop and build

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build.py
```

Mac builds require Python 3.12+ and the Xcode command-line tools to compile the Swift desktop host and vendored libusb source for a macOS 12 deployment target. This removes dependence on Homebrew’s binary deployment target; older-macOS runtime behavior still needs testing. Source-only launches use the browser unless the native host is supplied; `--no-browser` is available for test harnesses.

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. The build uses the system .NET Framework C# compiler and downloads the Microsoft WebView2 SDK from NuGet, checking its pinned SHA-256. Its redistributable libraries and licence are bundled beside the native window. Build on each target OS; PyInstaller does not cross-compile. Windows output is `dist/Dialpad/` (keep the EXE and its supporting files together). Mac output is `dist/Dialpad.app`. The GitHub Actions workflow builds and tests both target platforms, packages versioned ZIP files with checksums, and publishes a release when a version tag is pushed.

The app icon is an original editable SVG in `ui/icon.svg`. Generated Mac, Windows and PNG icons are in `assets/`; `assets/render_icon.py` regenerates them with Playwright/Chrome and the macOS icon tools. The native host also uses a small template keypad symbol in the menu bar.

The frontend is plain HTML/CSS/JavaScript. `app.py` handles authenticated local API requests, validation, and one-use expiring write previews. `core/protocol.py` encodes validated packets without device I/O. `core/transport.py` accesses only the supported keypad ID and reports failures without automatic retries. Tests mock hardware; they do not program the keypad.

## Sources and licences

Protocol derived from the MIT-licensed [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool); its attribution is in `core/THIRD_PARTY_LICENSE.txt`. Bundled libusb is LGPL-2.1-or-later and dynamically loaded; see its licence and source/replacement instructions in `core/LIBUSB-LICENSE.txt` and `core/TRANSPORT-NOTES.md`. Python and PyInstaller bundle their runtime notices in the distribution where applicable.

The supplier ZIP was inspected only as data and is excluded from Git and builds. See [initial review](research/REVIEW.md) and the archive hash inventory. It was never executed and has not been certified malware-free.

### macOS device-control permission

Copy/Paste and multi-tap delivery require **Privacy & Security → Device control & data access**, called **Accessibility** on earlier macOS. Dialpad checks the operating system's current permission on each action and while refreshing its menu; it never treats an old approval as permission. It requests the system prompt once, then shows a quiet menu status until access is granted. The menu provides **Device control permissions…** and **Show Dialpad in Finder**.

If the switch is already enabled but the app still lacks access after a development rebuild, remove the stale Dialpad entry and add the current `Dialpad.app` again. Reopen the app if macOS requests it. This is necessary because ad-hoc signatures identify a specific binary build, not a stable publisher. Repeatedly toggling the stale entry may not repair that identity mismatch.

For releases, set `DIALPAD_SIGNING_IDENTITY` to an installed Apple signing identity before running `build.py`; PyInstaller then signs the app and bundled executables with that identity. Reuse the same certificate identity and bundle identifier across updates. The local ad-hoc fallback explicitly warns that approvals may need renewal after rebuilding. For local development, `.signing-identity` can hold the certificate fingerprint as a persistent default; this file is Git-ignored and the private key remains in Keychain. The environment variable overrides it. A configured signing failure stops the build rather than falling back to ad-hoc signing. Apple Development signing is for local builds; public distribution needs Developer ID Application signing and notarization. Do not weaken signing requirements or modify the macOS privacy database to bypass consent.

## AI agent setup

Open **AI agent help** in the app and copy the instruction into Claude or Codex. The bundled [agent guide](ui/AGENT-GUIDE.md) documents local session discovery, supported actions, conflict-safe editing and preview/apply. `GET /api/agent` provides the guide and action vocabulary to authenticated local agents. No cloud service or repository checkout is required; the app must be running.
