# Six-key dial keypad review — 14 September 2026

## Findings
The connected USB device has VID 0x1189 and PID 0x8890. macOS exposes three HID devices: keyboard, keyboard plus consumer controls, and mouse. This is a strong match for the CH57x macro-keypad family; the exact firmware and physical key order have not been tested. No device settings were written and no keyboard events were recorded.

The original HTTP URL returned a 446,544-byte ZIP. HTTPS was unreachable during this review. The archive is stored as supplier-t1.zip.untrusted. Members were read in memory, with size limits, without extracting or executing programs. archive-inspection.json records member sizes, SHA-256 hashes and limited PE metadata.

The main program is a Windows .NET executable accompanied by HidLibrary.dll, Theraot.Core.dll, language resources, debug symbols and deployment manifests. The main Release/MINI KeyBoard.exe has no embedded PE certificate table. The app.publish copy has a certificate table; its signature validity was not checked.

Main EXE SHA-256: 4ae53d3a40921e4f57444c489fa1b38fe91a2e907feda17630450fc97a7cd7b1
ZIP SHA-256: d99cacb26eeca84c82b5087e70cd2325cc715da9743ff85e741ce38e823cd3c8

The main EXE hash matches the hash referenced by jonnytest1/minikeyboard. That repository describes two historic scanner findings. This review did not perform an antivirus scan or verify a current scan result. Neither a matching hash nor a static inventory proves the software safe. No files were uploaded to a third-party scanner.

## Build assessment
A custom configurator is feasible in principle. kriomant/ch57x-keyboard-tool documents support for this VID/PID and six-key, one-knob layouts. Its source provides a reference for programming packets and separate clockwise, counterclockwise and dial-press bindings. Compatibility still requires a controlled physical-device test.

Proposed first version: a visual six-key layout and dial, shortcut/media/mouse assignments, Mac and Windows profiles, local profile import/export, explicit Apply, and a test view. Aim for a self-contained Mac .app and Windows executable or portable folder.

The existing tool uses raw USB interrupt writes and requires USBDK on Windows. Wrapping it unchanged would not meet the no-install requirement. Investigate built-in HID access, using the supplier app's HidLibrary usage as supporting evidence. macOS reports only two-byte maximum HID output reports for the keyboard interfaces, whereas the reference programmer sends 64-byte USB packets. Transport behavior needs validation before promising driver-free support. HIDAPI supports both platforms but is not itself proof this device accepts programming through their HID APIs.

For this device family, ordinary bindings are written to the keypad so the configurator can exit. Arbitrary scripts and application-aware actions generally require a running host helper or OS automation. Do not promise reading/backing up the existing hardware mapping: no read-back capability was established.

## Sources
- https://github.com/jonnytest1/minikeyboard/issues/5
- https://github.com/jonnytest1/minikeyboard
- https://github.com/kriomant/ch57x-keyboard-tool
- https://raw.githubusercontent.com/kriomant/ch57x-keyboard-tool/master/src/main.rs
- https://raw.githubusercontent.com/kriomant/ch57x-keyboard-tool/master/src/keyboard/k8890.rs
- https://github.com/libusb/hidapi

No application has been built as part of this initial review. Next technical milestone: verify a native device connection and a controlled single-key write, then test key position, dial events and persistence before implementing full configuration writes.
