# Mac / Windows review — 2026-09-16

The shared profile validation, encoder, authenticated localhost API and reviewed hardware snapshots remain platform-independent. The Mac build was tested on this Apple Silicon Mac. Windows code was reviewed and tested using mocked operating-system calls; a Windows machine and keypad are still needed to validate actual HID programming and desktop behavior.

| Finding | Resolution | Evidence |
| --- | --- | --- |
| Tk can consume thread-level WM_HOTKEY messages before a polling callback | A dedicated thread now owns registration, GetMessage, dispatch and cleanup; Tk consumes a Python queue | Worker ownership, dispatch and failure-cleanup tests |
| Windows allowed competing companion instances | A nonblocking msvcrt byte lock now shares the existing session/reopen flow; the companion handles show_request | Mocked Windows locking/reopen tests; Mac flock regression |
| Default Windows text encoding could reject emoji/CJK setup names | Persistent and bundled JSON use explicit UTF-8 | Persistence roundtrip with a simulated cp1252 default |
| Homebrew libusb required macOS26 despite a native macOS12 target | Build the vendored libusb1.0.30 source with its upstream Xcode configuration, an explicit macOS12 deployment target and matching architecture | Packaged dylib LC_BUILD_VERSION reports minos12.0; packaged device discovery passes |

The Mac app remains signed with the configured Apple Development certificate. A Developer ID distribution build and notarization are separate from this local build. Build the Windows package on Windows; this Mac does not cross-compile a Windows executable. The Mac12 deployment target is a binary compatibility target, not a claim of runtime testing on Mac12.

Windows hotkey references: [RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey), [upstream Tcl message loop](https://github.com/tcltk/tcl/blob/core-8-6-branch/win/tclWinNotify.c). libusb build configuration and source list come from the vendored upstream Xcode/config.h and libusb/Makefile.am. No general keyboard monitor or hardware writes were used for validation.
