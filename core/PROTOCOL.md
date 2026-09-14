# Programming protocol

`encode_binding(control, action, layer=1)` is a pure encoder for the
`ch57x-2` protocol associated with VID/PID `1189:8890`. It never opens or writes
a device. Matching USB IDs is evidence for the protocol, not firmware proof.
Physical key order and writes still need hardware verification.

Each returned packet is exactly 64 bytes, padded with zeroes. Key IDs are 1–6;
the first dial uses 13 (counterclockwise), 14 (press), 15 (clockwise).
For layer 1, each binding starts `03 fe 01 01 01` and finishes `03 aa aa`.
Keyboard data includes an initial empty chord before the actual chord(s).
The encoded action byte combines the one-based layer in the upper nibble
with kind 1 (keyboard), 2 (media) or 3 (mouse). Wheel down uses signed byte
`ff`; wheel up uses `01`. Host natural-scrolling settings may reverse the
apparent scroll direction. Media values are little-endian consumer usages.

Public layers are conservatively limited to 1–3. Shortcuts use HID key usages,
so character interpretation follows the computer's keyboard layout. There is
no universal standard keyboard usage for Fn/Globe. A dictation action should
use a shortcut configured in the user's dictation app or operating system.
The optional sequence supports 1–5 shortcuts, without timing delays. It must
not be described as guaranteed press-and-hold or timed double-tap behavior.

## Transport contract

The reference raw USB transport first sends 64 zero bytes (exported as
`INITIALIZE_PACKET`), then each encoded packet, using interrupt OUT endpoint
`02` on a class 3, subclass 0, protocol 0 interface. It checks complete writes.
Opening the reference CLI's device handle also initializes it; do not use
that open operation for read-only discovery.

These raw USB buffers must not be automatically converted into feature
reports, trimmed, or prefixed with another report ID. HIDAPI expects the
first byte to be a report ID, but a driver-free implementation must establish
that its OS HID path accepts this device's programming packets. The prior
local review observed only two-byte maximum HID output reports; that is a
material mismatch with 64-byte programming packets. Success at enumeration
does not establish writing support. No read-back or firmware backup protocol
is provided here.

## Sources and licensing

- [Packet encoder and original byte fixtures](https://github.com/kriomant/ch57x-keyboard-tool/blob/master/src/keyboard/k8890.rs)
- [Packet padding, knob IDs, HID usages](https://github.com/kriomant/ch57x-keyboard-tool/blob/master/src/keyboard/mod.rs)
- [VID/PID and preferred endpoint](https://github.com/kriomant/ch57x-keyboard-tool/blob/master/src/config.rs)
- [Raw USB initialization and transport](https://github.com/kriomant/ch57x-keyboard-tool/blob/master/src/main.rs)
- [HIDAPI output-report contract](https://github.com/libusb/hidapi/blob/master/hidapi/hidapi.h)

Consulted 14 September 2026. Protocol adaptation retains the upstream MIT
notice in `THIRD_PARTY_LICENSE.txt`.

Modifier-only shortcuts use `key: "NONE"` with a nonempty modifier list. Control+Option uses modifier mask 0x05 and keycode 0x00, as supported by the upstream optional-key encoding. This does not prove physical key-hold behavior or emulate Apple Fn.
