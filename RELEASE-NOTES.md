Dialpad 0.1.1 — native Windows window, easier updates, rapid cycling and agent setup.

- Windows opens the same editor in its own app window, with a matching light title bar where supported. No browser tab or terminal is needed to use it.
- Close the editor to keep Dialpad in the system tray. Double-click the tray icon to reopen; its menu shows the active setup and Quit.
- `Update-Dialpad.ps1` downloads the latest Windows package, verifies its checksum and creates Start-menu entries for Dialpad and future updates. Saved setups are preserved; no admin rights requested.
- Rapid dial presses are queued one at a time, without the previous 1.2-second cooldown.
- AI agent help includes a copyable instruction, bundled API guide and authenticated local discovery for Claude or Codex.

**Windows:** download `Dialpad-0.1.1-windows-x64.zip`, extract the entire folder, and run `Dialpad/Dialpad.exe`, or use the updater. Requires .NET Framework 4.6.2+ and Microsoft Edge WebView2 Runtime. Dialpad explains how to obtain the runtime if missing. The EXE is unsigned; workplace policies may restrict it. Physical keypad programming on Windows remains unverified.

**Mac:** the GitHub-built package is ad-hoc signed and not notarized. It does not use the local development signing certificate. Switching signing identities may require renewed device-control permission. The matching libusb source archive accompanies the app.

Hardware changes still use preview and Apply. Settings stay local. ZIP checksums are provided in matching `.sha256` files.
