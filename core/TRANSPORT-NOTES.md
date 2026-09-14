# Device transport

The macOS programmer dynamically loads libusb 1.0.30, an LGPL-2.1-or-later library.
`LIBUSB-LICENSE.txt` contains its license. The library is unmodified; its corresponding
source is available at https://github.com/libusb/libusb/releases/tag/v1.0.30 and
https://github.com/libusb/libusb/archive/refs/tags/v1.0.30.tar.gz . When distributing a
binary, distribute that corresponding source archive alongside it as well. The
application's own licensing does not supersede libusb's license. Users may modify or replace
the dynamically loaded library and reverse engineer the application as necessary
to debug those library modifications, as provided by the LGPL.

Packaged builds keep the dylib as a separate file in the application bundle's
PyInstaller contents directory; it must not be statically linked. Replace that
`libusb-1.0.0.dylib` with a compatible build to use a modified version. Modifying a
signed application can require locally re-signing it. Development builds discover
the library using `ctypes.util.find_library`.

Enumeration reads descriptors and never calls open/claim/detach/reset on USB
devices. Explicit writes open and claim only the descriptor-matched non-boot HID
interface with interrupt-OUT endpoint 0x02. They do not detach drivers, reset a
device, or change its configuration. A busy interface produces an error. No input
events are read or monitored.

Verified on the connected Mac: raw USB descriptors identify interface 1 and a
64-byte endpoint 0x02. Opening, claiming interface 1, releasing, and closing also
succeeded without writes, driver detachment, or device resets. The sandbox hides raw USB devices, so the app must be run
normally outside the development sandbox. Native HID exposes only the three
input interfaces; those are rejected for programming. No physical writes have
been performed during development. Firmware behavior, physical key order, and
persistence still need a deliberate single-key test.

Windows uses built-in SetupAPI/HID enumeration and overlapped WriteFile with a
timeout on the vendor MI_01 collection. It is not tested on Windows. HID sends
report ID 3, already supplied by the encoder, padded to the advertised 65 bytes.
The raw-USB-only initial all-zero packet is omitted for native HID; no automatic
report-ID probing is performed. Native macOS SetReport is only available for a
qualifying vendor output interface; compatibility with interrupt-only firmware
is not established.

Reference protocol: https://github.com/kriomant/ch57x-keyboard-tool . Additional
native Windows transport evidence: https://github.com/civilian7/hid-macro-keypad .
The two references describe firmware variations; USB transmission success alone
does not verify the resulting mapping, and there is no mapping read-back.
