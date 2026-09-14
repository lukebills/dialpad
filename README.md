# Dialpad

A local six-key + dial configurator for AI coding. Built for the `1189:8890` CH57x-2 keypad family, with Claude Code and Codex starter layouts. Modern browser UI, local USB connection, no cloud service or account.

## Run on this Mac

Open `dist/Dialpad.app`. It opens a local browser tab. Use **Quit** in the app to stop its local server; closing the browser tab alone does not quit the launcher. No Python installation is needed for the packaged app.

The source version runs with Python 3.10+: `python3 app.py`. macOS source development additionally needs libusb; the packaged app includes it. Windows uses built-in HID APIs. Neither route executes the manufacturer's software.

## First use

1. Plug the keypad in by USB. Click Refresh if needed.
2. Load the Claude Code terminal, Codex terminal, or Codex desktop starting layout, and choose Mac or Windows. Loading a layout edits the app only.
3. Configure your dictation shortcut: all starter layouts use **Wispr Flow Hands-free mode**. On Mac, assign **Control + Option + Space** in Flow Settings → General → Shortcuts → Hands-free mode. On Windows the suggested default is **Control + Windows + Space**; verify it in Flow settings. Tap once to start, tap again to stop and paste. Escape cancels and discards a dictation in progress. Dialpad triggers Flow; it does not transcribe audio itself.
4. Click a key and choose its action or record a shortcut. The dial supports real mouse-wheel up/down and an independent press action.
5. Start with **Selected control only**, click **Review changes**, verify the proposed binding, then **Apply to keypad**. Test it in the scratch area and your coding app. Key positions and wheel direction need a physical check.
6. Export your profile to keep a copy. Import restores the editor settings; Apply writes them to the keypad.

The initial layout is Wispr Flow, Enter, Escape, New line, Paste, and Transcript (Claude terminal) or Tab (Codex terminal). Dial rotation scrolls and its press sends Tab. Desktop profiles use separate shortcuts. Escape has context-specific behavior, not a universal rejection action. See [shortcut research](research/KEY-LAYOUT.md).

Profiles are **not** read from the hardware. Applying replaces the selected controls on the selected layer. The app cannot back up the existing device configuration, verify it by read-back, or automatically roll back an interrupted write. A completed transfer must be checked on the physical keypad. Layers 2 and 3 are only useful if your hardware supports switching layers. Profiles do not switch automatically with the foreground application.

## Portability and current limits

- macOS: native IOKit enumeration plus bundled libusb for the raw programming interface. No driver replacement, firmware flashing or manufacturer executable. Packaged builds match the Mac architecture used to build them.
- Windows: native HID output path implemented, but not tested on Windows hardware. Some firmware versions may not expose a compatible native programming interface. Do not assume the Mac-tested raw transport proves Windows compatibility.
- Portable builds open in your default browser and communicate only with a server bound to `127.0.0.1` using a per-launch secret. Internet is not required for configuration.
- The local build is ad-hoc signed, not Apple-notarized. Public distribution with a smooth first launch needs appropriate signing/notarization; we do not disable Gatekeeper.
- No global key listener, background dictation engine, arbitrary script execution, or app-aware automation. The test area only sees input while it has focus.
- Edits are held in the browser tab; export before quitting to keep them. Profile exports are app settings, not hardware backups.

## Develop and build

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build.py
```

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Build on each target OS; PyInstaller does not cross-compile. Windows output is `dist/Dialpad/` (keep the EXE and its supporting files together). Mac output is `dist/Dialpad.app`. The GitHub Actions workflow can build both after this repository is hosted on GitHub; no remote is configured automatically.

The frontend is plain HTML/CSS/JavaScript. `app.py` handles authenticated local API requests, validation, and one-use expiring write previews. `core/protocol.py` encodes validated packets without device I/O. `core/transport.py` accesses only the supported keypad ID and reports failures without automatic retries. Tests mock hardware; they do not program the keypad.

## Sources and licences

Protocol derived from the MIT-licensed [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool); its attribution is in `core/THIRD_PARTY_LICENSE.txt`. Bundled libusb is LGPL-2.1-or-later and dynamically loaded; see its licence and source/replacement instructions in `core/LIBUSB-LICENSE.txt` and `core/TRANSPORT-NOTES.md`. Python and PyInstaller bundle their runtime notices in the distribution where applicable.

The supplier ZIP was inspected only as data and is excluded from Git and builds. See [initial review](research/REVIEW.md) and the archive hash inventory. It was never executed and has not been certified malware-free.
