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
