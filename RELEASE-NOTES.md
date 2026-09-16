Dialpad 0.1.0 — first portable release for the six-key CH57x keypad with a clickable dial.

- Live setup editor with autosave, preloaded layouts and configurable dial cycling.
- Single-, double- and triple-tap actions, including plain-text Copy / Paste / Cut.
- Mac menu-bar companion and Windows background companion.

**Windows:** download `Dialpad-0.1.0-windows-x64.zip`, extract the whole folder, and run `Dialpad/Dialpad.exe`. No Python installation is required. Keep the supporting files beside the executable. The Windows app is not Authenticode-signed; Windows or workplace policies may show a warning or restrict it. Actual keypad programming on Windows remains unverified.

**Mac:** the GitHub-built Mac package is ad-hoc signed and not notarized. It does not use the development certificate of the local build. Changing from a differently signed build can require renewed device-control permission. The package architecture is included in its filename. The matching libusb source archive is provided alongside the app.

App settings save locally. Hardware changes require review and Apply. Closing the editor keeps the companion running; Quit stops it. Checksums are provided in the matching `.sha256` files.
